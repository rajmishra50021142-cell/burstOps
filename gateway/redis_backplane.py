"""Upgrade B: Redis backplane — leader polls, followers read.

Separates the CONTROL PLANE (one poller, one state machine, one PI
controller) from the DATA PLANE (N stateless replicas that just route).
Redis carries the decision between them; the request path does ZERO Redis
I/O — followers keep a local cached copy refreshed in the background.

Degradation is layered so the existing semantics survive:
  1. Fresh shared state (age <= REDIS_STATE_MAX_AGE_MS) -> use it.
  2. Stale/unreadable -> follower polls Prometheus itself (today's
     single-replica behaviour — worst case of a Redis outage is the
     behaviour we already shipped).
  3. Its own polling also stale past STALE_STATE_GRACE -> existing
     fail-open-to-BURST fires, unchanged.

REDIS_URL empty/unset (the default) disables the backplane entirely.
Redis down at startup must not crash the pod: log once, metric to 0, retry
in the background. No exception ever escapes to the request path.

HONEST LIMITATION (docs/upgrade-b-notes.md): Redis leader election is NOT
consensus. A leader that pauses past the TTL can still believe it leads
while another takes over — two writers briefly coexist. The generation
counter bounds the damage and the state is reconstructible in one poll
cycle. The correct-but-heavier primitive is a Kubernetes Lease via the
coordination API — named as the alternative, deliberately not built.
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
REDIS_LEADER_TTL_MS = 6000              # survives two missed renewals
REDIS_LEADER_RENEW_MS = 2000            # matches POLL_INTERVAL
REDIS_STATE_MAX_AGE_MS = 10000          # ~5 poll cycles before distrust
REDIS_SOCKET_TIMEOUT_S = 0.5            # a hung Redis must not stall the loop
GATEWAY_INSTANCE_ID = f"{socket.gethostname()}-{os.getpid()}"

# CAS renewal as a Lua script so check+extend is ONE atomic step.
# SET key val XX PX ttl would be WRONG: XX succeeds whenever the key exists
# — it never checks WHO owns it — so a follower could silently steal an
# active lease.
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
        # snapshot NOW: the module-level default is shared, so each
        # backplane must own its identity (tests construct several)
        self._instance_id = GATEWAY_INSTANCE_ID
        self._client = aioredis.Redis.from_url(
            url,
            socket_timeout=REDIS_SOCKET_TIMEOUT_S,
            socket_connect_timeout=REDIS_SOCKET_TIMEOUT_S,
            decode_responses=True,
        )
        self.is_leader = False
        self.shared = {"mode": None, "deflect_ratio": None, "updated_at_ms": 0, "generation": 0}
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
            # someone else holds the lease: demote and reset the gauge —
            # a stale is_leader=1 on a follower breaks the "sums to 1" contract
            self.is_leader = False
            try:
                self._m.gateway_is_leader.set(0)
            except Exception:  # noqa: BLE001
                pass
        return bool(ok)

    async def renew_lease(self) -> bool:
        """CAS renewal: 0 return = I am no longer the leader — demote
        immediately, never retry into a second leader."""
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
        """Graceful shutdown: CAS delete so a restart hands over in
        milliseconds instead of waiting out the TTL."""
        try:
            await self._release_script(
                keys=[REDIS_LEADER_KEY], args=[self._instance_id]
            )
            self._set_up(True)
        except Exception:  # noqa: BLE001
            self._err("release")
        self.is_leader = False

    # ---- state publish / subscribe -------------------------------------------
    async def publish_state(self, mode_value: str, deflect_ratio: float, cpu: float) -> None:
        """Leader only: write the decision hash + notify. Generation from
        INCR; followers ignore any read whose generation is lower than the
        highest they've seen (guards a briefly-resurrected old leader)."""
        try:
            gen = await self._client.incr("burstops:generation")
            await self._client.hset(
                REDIS_STATE_KEY,
                mapping={
                    "mode": mode_value,
                    "deflect_ratio": f"{deflect_ratio:.6f}",
                    "cpu_observed": f"{cpu:.4f}",
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
        """Follower backstop poll (pub/sub is fire-and-forget; a follower
        that misses a message during reconnect would otherwise stay stale
        forever). Belt and braces; the poll costs nothing."""
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
                return  # stale writer — ignore
            self._last_seen_generation = gen
            self.shared = {
                "mode": data.get("mode"),
                "deflect_ratio": float(data.get("deflect_ratio", 0.0)),
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
    """Factory: returns None when REDIS_URL is empty (backplane off — the
    default — and the gateway behaves precisely as before)."""
    url = os.environ.get("REDIS_URL", REDIS_URL).strip()
    if not url:
        return None
    try:
        return RedisBackplane(url, metrics_module, state_owner)
    except Exception as exc:  # noqa: BLE001 — never crash the pod
        logger.warning("redis backplane construction failed (running local-only): %s", exc)
        return None
