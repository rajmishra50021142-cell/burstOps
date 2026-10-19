"""Upgrade B: Redis backplane — leader polls, followers read.

Separates the CONTROL PLANE (one poller, one state machine, one PI
controller) from the DATA PLANE (N stateless replicas that just route).
Redis carries the decision between them; the request path does ZERO Redis
I/O — followers keep a local cached copy refreshed in the background.

Also coordinates capacity slots and Golden Trio distributed state:
- Active base compute slots (out of MAX_BASE_COMPUTE_SLOTS = 10)
- AIMD dynamic burst threshold theta(t)
- Composite capacity utilization U_total
"""
import asyncio
import logging
import os
import socket
import time

logger = logging.getLogger("burstops.redis_backplane")

# ---- constants (env-overridable via gateway_entrypoint.py) -----------------
REDIS_URL = ""                          # empty => backplane off (default)
REDIS_LEADER_KEY = "burstops:leader"
REDIS_STATE_KEY = "burstops:state"
REDIS_ACTIVE_SLOTS_KEY = "burstops:active_compute_slots"
MAX_BASE_COMPUTE_SLOTS = int(os.environ.get("MAX_BASE_COMPUTE_SLOTS", "10"))
REDIS_LEADER_TTL_MS = 6000              # survives two missed renewals
REDIS_LEADER_RENEW_MS = 2000            # matches POLL_INTERVAL
REDIS_STATE_MAX_AGE_MS = 10000          # ~5 poll cycles before distrust
REDIS_SOCKET_TIMEOUT_S = 0.5            # a hung Redis must not stall the loop
GATEWAY_INSTANCE_ID = f"{socket.gethostname()}-{os.getpid()}"

# CAS renewal as a Lua script so check+extend is ONE atomic step.
_RENEW_LEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('pexpire', KEYS[1], ARGV[2])
else
  return 0
end
"""

_RELEASE_LEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""


class RedisBackplane:
    """All Redis interaction lives here. Every call wrapped — no exception
    escapes; gateway_redis_errors_total{op} counts failures."""

    def __init__(self, url: str, metrics, state_owner) -> None:
        import redis.asyncio as aioredis

        self._url = url
        self._m = metrics                    # gateway module (metrics + state)
        self._state_owner = state_owner       # the RoutingState instance
        self._instance_id = GATEWAY_INSTANCE_ID
        self._client = aioredis.Redis.from_url(
            url,
            socket_timeout=REDIS_SOCKET_TIMEOUT_S,
            socket_connect_timeout=REDIS_SOCKET_TIMEOUT_S,
            decode_responses=True,
        )
        self.is_leader = False
        self.shared = {
            "mode": None,
            "deflect_ratio": None,
            "active_slots": 0,
            "dynamic_threshold": 0.80,
            "composite_util": 0.0,
            "updated_at_ms": 0,
            "generation": 0,
        }
        self._last_seen_generation = 0
        self._renew_script = self._client.register_script(_RENEW_LEASE_LUA)
        self._release_script = self._client.register_script(_RELEASE_LEASE_LUA)

    @property
    def instance_id(self) -> str:
        return self._instance_id

    # ---- metrics helpers ----------------------------------------------------
    def _err(self, op: str) -> None:
        try:
            self._m.gateway_redis_errors_total.labels(op=op).inc()
        except Exception:  # noqa: BLE001
            pass

    def _set_up(self, up: bool) -> None:
        try:
            self._m.gateway_redis_up.set(1 if up else 0)
        except Exception:  # noqa: BLE001
            pass

    # ---- leader election ----------------------------------------------------
    async def try_acquire(self) -> bool:
        try:
            ok = await self._client.set(
                REDIS_LEADER_KEY, self._instance_id, nx=True, px=REDIS_LEADER_TTL_MS
            )
            up = True
        except Exception:  # noqa: BLE001
            self._err("acquire")
            up = None
        if up is None:
            self._set_up(False)
            return False
        self._set_up(True)
        if ok:
            self.is_leader = True
            try:
                self._m.gateway_is_leader.set(1)
                self._m.gateway_leader_elections_total.inc()
            except Exception:  # noqa: BLE001
                pass
        elif self.is_leader:
            self.is_leader = False
            try:
                self._m.gateway_is_leader.set(0)
            except Exception:  # noqa: BLE001
                pass
        return bool(ok)

    async def renew_lease(self) -> bool:
        try:
            r = await self._renew_script(
                keys=[REDIS_LEADER_KEY], args=[self._instance_id, REDIS_LEADER_TTL_MS]
            )
            self._set_up(True)
        except Exception:  # noqa: BLE001
            self._err("renew")
            return False
        if not r:
            if self.is_leader:
                self.is_leader = False
                try:
                    self._m.gateway_is_leader.set(0)
                except Exception:  # noqa: BLE001
                    pass
            return False
        return True

    async def release_lease(self) -> None:
        try:
            await self._release_script(
                keys=[REDIS_LEADER_KEY], args=[self._instance_id]
            )
            self._set_up(True)
        except Exception:  # noqa: BLE001
            self._err("release")
        self.is_leader = False

    # ---- capacity slots tracking ---------------------------------------------
    async def reset_active_slots(self) -> int:
        try:
            await self._client.set(REDIS_ACTIVE_SLOTS_KEY, "0")
            await self._client.set("aks:active_slots", "0")
            self._set_up(True)
            return 0
        except Exception:
            self._err("reset_slots")
            return 0

    async def incr_active_slots(self) -> int:
        try:
            val = await self._client.incr(REDIS_ACTIVE_SLOTS_KEY)
            try:
                await self._client.set("aks:active_slots", str(val))
            except Exception:
                pass
            self._set_up(True)
            return int(val)
        except Exception:
            self._err("incr_slots")
            return 0

    async def decr_active_slots(self) -> int:
        try:
            if hasattr(self._client, "decr"):
                val = await self._client.decr(REDIS_ACTIVE_SLOTS_KEY)
            else:
                cur = await self._client.get(REDIS_ACTIVE_SLOTS_KEY)
                val = max(0, int(cur or 0) - 1)
                await self._client.set(REDIS_ACTIVE_SLOTS_KEY, str(val))
            val_clamped = max(0, int(val))
            try:
                await self._client.set("aks:active_slots", str(val_clamped))
            except Exception:
                pass
            self._set_up(True)
            return val_clamped
        except Exception:
            self._err("decr_slots")
            return 0

    async def get_active_slots(self) -> int:
        try:
            val = await self._client.get(REDIS_ACTIVE_SLOTS_KEY)
            if val is None:
                val = await self._client.get("aks:active_slots")
            self._set_up(True)
            return int(val) if val is not None else 0
        except Exception:
            self._err("get_slots")
            return 0

    async def register_stream_lease(self, stream_id: str, ttl: float = 2.5) -> None:
        try:
            await self._client.set(f"burstops:lease:{stream_id}", "1", ex=int(ttl + 1))
            self._set_up(True)
        except Exception:
            self._err("lease")

    async def clear_stream_leases(self, client_id: str = None) -> None:
        try:
            if client_id:
                keys = await self._client.keys(f"burstops:lease:{client_id}:*")
            else:
                keys = await self._client.keys("burstops:lease:*")
            if keys:
                await self._client.delete(*keys)
            self._set_up(True)
        except Exception:
            self._err("clear_leases")

    # ---- state publish / subscribe -------------------------------------------
    async def publish_state(
        self,
        mode_value: str,
        deflect_ratio: float,
        cpu: float,
        active_slots: int = 0,
        dynamic_threshold: float = 0.80,
        composite_util: float = 0.0,
    ) -> None:
        try:
            gen = await self._client.incr("burstops:generation")
            await self._client.hset(
                REDIS_STATE_KEY,
                mapping={
                    "mode": mode_value,
                    "deflect_ratio": f"{deflect_ratio:.6f}",
                    "cpu_observed": f"{cpu:.4f}",
                    "active_slots": str(active_slots),
                    "dynamic_threshold": f"{dynamic_threshold:.4f}",
                    "composite_util": f"{composite_util:.4f}",
                    "updated_at_ms": str(int(time.time() * 1000)),
                    "leader_id": self._instance_id,
                    "generation": str(gen),
                },
            )
            await self._client.publish(
                "burstops:state:updates",
                f"{gen}:{mode_value}:{deflect_ratio:.6f}",
            )
            self._set_up(True)
        except Exception:  # noqa: BLE001
            self._err("publish")

    async def refresh_shared_state(self) -> None:
        try:
            data = await self._client.hgetall(REDIS_STATE_KEY)
            self._set_up(True)
        except Exception:  # noqa: BLE001
            self._err("read")
            return
        if not data:
            return
        try:
            gen = int(data.get("generation", "0"))
            if gen < self._last_seen_generation:
                return
            self._last_seen_generation = gen
            self.shared = {
                "mode": data.get("mode"),
                "deflect_ratio": float(data.get("deflect_ratio", 0.0)),
                "active_slots": int(data.get("active_slots", "0")),
                "dynamic_threshold": float(data.get("dynamic_threshold", "0.80")),
                "composite_util": float(data.get("composite_util", "0.0")),
                "updated_at_ms": int(data.get("updated_at_ms", "0")),
                "generation": gen,
            }
            age_s = (time.time() * 1000 - self.shared["updated_at_ms"]) / 1000.0
            try:
                self._m.gateway_shared_state_age_seconds.set(max(age_s, 0.0))
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            self._err("parse")

    def shared_state_fresh(self) -> bool:
        age_ms = time.time() * 1000 - self.shared["updated_at_ms"]
        return 0 <= age_ms <= REDIS_STATE_MAX_AGE_MS


def build_backplane(metrics_module, state_owner):
    url = os.environ.get("REDIS_URL", REDIS_URL).strip()
    if not url:
        return None
    try:
        return RedisBackplane(url, metrics_module, state_owner)
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis backplane construction failed (running local-only): %s", exc)
        return None
