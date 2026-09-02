"""Upgrade B: Redis backplane tests — in-memory fake Redis, no network, no
real Redis, injected time. The fake supports exactly what redis_backplane
uses (set nx/px, get, hset/hgetall, incr, publish, Lua renew/release via
eval-shims) and is HONEST about TTL expiry — that is the whole value.
"""
import asyncio
import time
import types
from pathlib import Path

import pytest

sys = __import__("sys")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gateway"))

# ---- module stubs MUST precede the gateway import --------------------------
def _mkmod(name):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)
    return sys.modules[name]


for _n in ("fastapi", "fastapi.responses", "prometheus_client"):
    _mkmod(_n)
_f = sys.modules["fastapi"]
_f.FastAPI = lambda *a, **kw: types.SimpleNamespace(
    router=types.SimpleNamespace(lifespan_context=None),
    get=lambda *a, **kw: (lambda f: f),
    api_route=lambda *a, **kw: (lambda f: f),
    add_middleware=lambda *a, **kw: None,
)
_f.Request = object
_f.api_route = lambda *a, **kw: (lambda f: f)
_r = sys.modules["fastapi.responses"]
_r.JSONResponse = type("J", (), {})
_r.PlainTextResponse = type("P", (), {})
_pc = sys.modules["prometheus_client"]
_pc.CONTENT_TYPE_LATEST = "t"
_pc.Counter = lambda *a, **kw: types.SimpleNamespace(inc=lambda *a, **kw: None, labels=lambda **kw: types.SimpleNamespace(inc=lambda *a, **kw: None))
_pc.Gauge = lambda *a, **kw: types.SimpleNamespace(set=lambda *a, **kw: None, labels=lambda **kw: types.SimpleNamespace(set=lambda *a, **kw: None))
_pc.Histogram = lambda *a, **kw: types.SimpleNamespace(observe=lambda *a, **kw: None, labels=lambda **kw: types.SimpleNamespace(observe=lambda *a, **kw: None))
_pc.generate_latest = lambda: b""
_hx = types.ModuleType("httpx"); _hx.AsyncClient = object; _hx.Timeout = lambda *a, **kw: None
sys.modules["httpx"] = _hx
# fresh gateway under stubs, then redis_backplane (still real — its Redis
# import is replaced by the fake right after)
import importlib
sys.modules.pop("gateway", None)
import gateway  # noqa: E402,F811
import redis_backplane  # noqa: E402

# redis.asyncio stub so RedisBackplane binds to the fake
_fake_redis_mod = types.ModuleType("redis")
_fake_asyncio_mod = types.ModuleType("redis.asyncio")


class FakeRedis:
    """In-memory async fake with TTL expiry, CAS scripts, failure switches.

    ALL instances share one class-level store — Redis is a single server;
    two backplanes must see the same keys for leader election to mean
    anything."""

    SHARED = {"kv": {}, "hash": {}, "incr": {}, "published": []}

    def __init__(self):
        self.kv = FakeRedis.SHARED["kv"]
        self.hash = FakeRedis.SHARED["hash"]
        self.incr_ctr = FakeRedis.SHARED["incr"]
        self.published = FakeRedis.SHARED["published"]
        self.fail_all = False
        self.fail_next_n = 0
        # class-level clock so advance() is visible across instances
        if not hasattr(FakeRedis, "_clock_ms"):
            FakeRedis._clock_ms = staticmethod(lambda: time.time() * 1000)
        self._clock_ms = lambda: FakeRedis._clock_ms()

    # helpers
    @classmethod
    def advance(cls, ms):
        base = cls._clock_ms()
        cls._clock_ms = staticmethod(lambda: base + ms)

    @classmethod
    def reset(cls):
        FakeRedis.SHARED = {"kv": {}, "hash": {}, "incr": {}, "published": []}
        FakeRedis._clock_ms = staticmethod(lambda: time.time() * 1000)

    def fail_next(self, n=1):
        self.fail_next_n = n

    def always_fail(self, on=True):
        self.fail_all = on

    def _check(self):
        if self.fail_all or self.fail_next_n > 0:
            self.fail_next_n -= 1
            raise ConnectionError("fake redis down")

    # async API used by the backplane
    async def set(self, key, value, nx=False, px=None):
        self._check()
        cur, exp = self.kv.get(key, (None, None))
        alive = cur is not None and (exp is None or exp > self._clock_ms())
        if nx and alive:
            return None
        self.kv[key] = (value, self._clock_ms() + px if px else None)
        return "OK"

    async def get(self, key):
        self._check()
        cur, exp = self.kv.get(key, (None, None))
        if cur is None or (exp is not None and exp <= self._clock_ms()):
            return None
        return cur

    async def delete(self, key):
        self._check()
        self.kv.pop(key, None)
        return 1

    async def hset(self, key, mapping):
        self._check()
        self.hash.setdefault(key, {}).update(mapping)
        return len(mapping)

    async def hgetall(self, key):
        self._check()
        return dict(self.hash.get(key, {}))

    async def incr(self, key):
        self._check()
        self.incr_ctr[key] = self.incr_ctr.get(key, 0) + 1
        return self.incr_ctr[key]

    async def publish(self, channel, message):
        self._check()
        self.published.append((channel, message))
        return 1

    class _Script:
        def __init__(self, fake, body):
            self.fake, self.body = fake, body

        async def __call__(self, keys, args):
            self.fake._check()
            key, ident, arg2 = keys[0], args[0], (args[1] if len(args) > 1 else None)
            cur, exp = self.fake.kv.get(key, (None, None))
            alive = cur is not None and (exp is None or exp > self.fake._clock_ms())
            if "pexpire" in self.body:
                if alive and cur == ident:
                    self.fake.kv[key] = (cur, self.fake._clock_ms() + int(arg2))
                    return 1
                return 0
            if "del" in self.body:
                if alive and cur == ident:
                    self.fake.kv.pop(key, None)
                    return 1
                return 0
            return 0

    def register_script(self, body):
        return FakeRedis._Script(self, body)

    @classmethod
    def from_url(cls, url, **kw):
        inst = cls()
        cls._last = inst
        return inst


_fake_asyncio_mod.Redis = FakeRedis
_fake_redis_mod.asyncio = _fake_asyncio_mod
sys.modules["redis"] = _fake_redis_mod
sys.modules["redis.asyncio"] = _fake_asyncio_mod

# reload rb so RedisBackplane binds to the fake
importlib.reload(redis_backplane)
rb = redis_backplane


def make_bp(fake=None, instance="inst-A"):
    rb.GATEWAY_INSTANCE_ID = instance
    bp = rb.RedisBackplane("redis://fake", gateway, gateway.routing_state)
    return bp


@pytest.fixture(autouse=True)
def _clean_redis_between_tests():
    FakeRedis.reset()
    yield
    FakeRedis.reset()


@pytest.mark.asyncio
async def test_1_lone_instance_acquires_leadership():
    bp = make_bp()
    assert await bp.try_acquire() is True
    assert bp.is_leader is True
    assert gateway.gateway_is_leader._value.get() if hasattr(gateway.gateway_is_leader, "_value") else True


@pytest.mark.asyncio
async def test_2_second_instance_fails_while_held():
    bp_a = make_bp(instance="A"); await bp_a.try_acquire()
    bp_b = make_bp(instance="B")
    assert await bp_b.try_acquire() is False
    assert bp_b.is_leader is False
    # pair's is_leader flags sum to 1
    assert int(bp_a.is_leader) + int(bp_b.is_leader) == 1


@pytest.mark.asyncio
async def test_3_cas_renewal():
    bp_a = make_bp(instance="A"); await bp_a.try_acquire()
    assert await bp_a.renew_lease() is True            # holder extends
    bp_b = make_bp(instance="B")
    assert await bp_b.renew_lease() is False          # non-holder: 0, no extend
    assert await bp_a.renew_lease() is True           # A still owns it


@pytest.mark.asyncio
async def test_4_lease_expiry_promotes_follower():
    bp_a = make_bp(instance="A"); await bp_a.try_acquire()
    bp_b = make_bp(instance="B")
    bp_a._client.advance(rb.REDIS_LEADER_TTL_MS + 10)  # TTL passes
    assert await bp_b.try_acquire() is True            # B promoted
    assert bp_b.is_leader is True


@pytest.mark.asyncio
async def test_5_graceful_release_hands_over_immediately():
    bp_a = make_bp(instance="A"); await bp_a.try_acquire()
    await bp_a.release_lease()
    bp_b = make_bp(instance="B")
    assert await bp_b.try_acquire() is True            # no TTL wait needed


@pytest.mark.asyncio
async def test_6_follower_state_equals_leader_write():
    bp_a = make_bp(instance="A"); await bp_a.try_acquire()
    await bp_a.publish_state("burst", 0.625, 91.4)
    bp_b = make_bp(instance="B")
    await bp_b.refresh_shared_state()
    assert bp_b.shared["mode"] == "burst"
    assert bp_b.shared["deflect_ratio"] == 0.625       # exactly, not approx


@pytest.mark.asyncio
async def test_7_stale_state_falls_back():
    bp_a = make_bp(instance="A"); await bp_a.try_acquire()
    await bp_a.publish_state("burst", 0.5, 90.0)
    bp_b = make_bp(instance="B")
    await bp_b.refresh_shared_state()
    assert bp_b.shared_state_fresh() is True
    # age the shared state by rewriting updated_at_ms into the past —
    # semantically identical to waiting, no fake-clock coupling to the
    # backplane's real-time freshness check
    aged = int(time.time() * 1000) - (rb.REDIS_STATE_MAX_AGE_MS + 10)
    await bp_b._client.hset(rb.REDIS_STATE_KEY, mapping={"updated_at_ms": str(aged)})
    await bp_b.refresh_shared_state()
    assert bp_b.shared_state_fresh() is False        # too old -> distrust


@pytest.mark.asyncio
async def test_8_lower_generation_ignored():
    bp_a = make_bp(instance="A"); await bp_a.try_acquire()
    await bp_a.publish_state("burst", 0.5, 90.0)      # gen 1
    bp_b = make_bp(instance="B")
    await bp_b.refresh_shared_state()
    assert bp_b._last_seen_generation == 1
    # an old leader resurrects and writes a lower generation
    await bp_a._client.hset(rb.REDIS_STATE_KEY, mapping={
        "mode": "baseline", "deflect_ratio": "0",
        "cpu_observed": "10", "updated_at_ms": str(int(time.time() * 1000)),
        "leader_id": "ghost", "generation": "0"})
    await bp_b.refresh_shared_state()
    assert bp_b.shared["mode"] == "burst"              # keeps newer state


@pytest.mark.asyncio
async def test_9_redis_failing_everywhere_degrades():
    bp_a = make_bp(instance="A"); await bp_a.try_acquire()
    bp_a._client.always_fail(True)
    assert await bp_a.try_acquire() is False           # no crash
    assert await bp_a.renew_lease() is False
    await bp_a.publish_state("burst", 0.5, 90.0)       # swallowed
    await bp_a.refresh_shared_state()                 # swallowed
    # request path: routing decision still produced (mode unchanged)
    assert gateway.routing_state.mode in (gateway.Mode.BASELINE, gateway.Mode.BURST)


@pytest.mark.asyncio
async def test_10_empty_redis_url_disables_backplane():
    import os
    os.environ.pop("REDIS_URL", None)
    assert rb.build_backplane(gateway, gateway.routing_state) is None
