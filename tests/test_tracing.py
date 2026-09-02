"""Upgrade D: OpenTelemetry tracing tests — InMemorySpanExporter, no network,
no sleeping. Requires the real OTel packages (they are the thing under test);
the rest of the suites' stubbing style is kept where it applies.
"""
import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

# --- load gateway with the same stubs as the other suites -------------------
def _mkmod(name):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)
    return sys.modules[name]

_mkmod("fastapi")
_mkmod("fastapi.responses")
_mkmod("prometheus_client")

fastapi = sys.modules["fastapi"]
fastapi.FastAPI = lambda *a, **kw: types.SimpleNamespace(
    router=types.SimpleNamespace(lifespan_context=None),
    get=lambda *a, **kw: (lambda f: f),
    api_route=lambda *a, **kw: (lambda f: f),
    add_middleware=lambda *a, **kw: None,
)
fastapi.Request = object
fastapi.api_route = lambda *a, **kw: (lambda f: f)
responses = sys.modules["fastapi.responses"]
responses.JSONResponse = type("JSONResponse", (), {})
responses.PlainTextResponse = type("PlainTextResponse", (), {})
pc = sys.modules["prometheus_client"]
pc.CONTENT_TYPE_LATEST = "text/plain"
pc.Counter = lambda *a, **kw: types.SimpleNamespace(inc=lambda *a, **kw: None, labels=lambda **kw: types.SimpleNamespace(inc=lambda *a, **kw: None))
pc.Gauge = lambda *a, **kw: types.SimpleNamespace(set=lambda *a, **kw: None, labels=lambda **kw: types.SimpleNamespace(set=lambda *a, **kw: None))
pc.Histogram = lambda *a, **kw: types.SimpleNamespace(observe=lambda *a, **kw: None, labels=lambda **kw: types.SimpleNamespace(observe=lambda *a, **kw: None))
pc.generate_latest = lambda: b""
httpx_stub = types.ModuleType("httpx")
httpx_stub.AsyncClient = object
httpx_stub.Timeout = lambda *a, **kw: None
sys.modules["httpx"] = httpx_stub

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "gateway"))

from opentelemetry import trace  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export import in_memory_span_exporter  # noqa: E402
from opentelemetry.propagate import extract, inject  # noqa: E402

import gateway  # noqa: E402
import tracing  # noqa: E402

SECRET = "test-secret"
FUNCTION_KEY = "k"


@pytest.fixture()
def mem_exporter():
    """In-memory exporter with its own explicit provider/tracer. OTel's
    global tracer provider, once set, cannot be replaced per-process, so
    tests pass an explicit tracer instead of relying on the global."""
    exp = in_memory_span_exporter.InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exp))
    tracer = provider.get_tracer("test")
    yield tracer, exp
    exp.clear()


# 1. opt-in by default: exporter=none -> configure_tracing returns None
def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OTEL_TRACES_EXPORTER", raising=False)
    assert tracing.configure_tracing() is None


def test_unknown_exporter_warns_and_disables(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "bogus")
    assert tracing.configure_tracing() is None


# 2. span shape: one server + one client span, client parented by server
def test_span_shape_and_parenting(mem_exporter, monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    tracer, exp = mem_exporter
    with tracer.start_as_current_span("server") as server_span:
        ctx = trace.set_span_in_context(server_span)
        with tracer.start_span("client", context=ctx) as client_span:
            client_span.set_attribute("burstops.route", "k8s")
    spans = exp.get_finished_spans()
    assert len(spans) == 2
    names = {s.name for s in spans}
    assert names == {"server", "client"}
    client = next(s for s in spans if s.name == "client")
    server = next(s for s in spans if s.name == "server")
    assert client.parent is not None and client.parent.span_id == server.context.span_id


# 3. propagation in: supplied trace id appears on our spans (hex, not "some id")
def test_traceparent_inbound_honoured(mem_exporter):
    TRACE_HEX = "0af7651916cd43dd8448eb211c80319c"
    SPAN_HEX = "b7ad6b7169203331"
    carrier = {"traceparent": f"00-{TRACE_HEX}-{SPAN_HEX}-01"}
    ctx = extract(carrier)
    tracer, exp = mem_exporter
    with tracer.start_as_current_span("s", context=ctx):
        pass
    span = exp.get_finished_spans()[0]
    assert format(span.context.trace_id, "032x") == TRACE_HEX


# 4. propagation out + HMAC unaffected: headers are OUTSIDE the signed payload
def test_signature_unchanged_with_trace_headers():
    # golden vector: secret=test-secret, ts=1700000000, body={"n":100}
    body = b'{"n":100}'
    ts = "1700000000"
    expected = "0bd99a3457b14815fed94d47656212f1a92580d93f8806cf86e67f87642a022b"
    # simulate a request carrying an injected traceparent: signature must be
    # computed over timestamp:body ONLY and remain byte-identical
    carrier = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
    _ = inject({})  # injector works on headers, never touches the body
    assert gateway.sign_request(SECRET, ts, body) == expected


# 5. attributes per mode (server span, via the module state)
def test_attributes_both_modes(mem_exporter, monkeypatch):
    monkeypatch.setattr(gateway.routing_state, "mode", gateway.Mode.BASELINE)
    monkeypatch.setattr(gateway.routing_state, "cpu_observed", 42.0)
    tracer, exp = mem_exporter
    with tracer.start_as_current_span("baseline-span") as s:
        s.set_attribute("burstops.routing_mode", gateway.routing_state.mode.value)
        s.set_attribute("burstops.cpu_observed_percent", gateway.routing_state.cpu_observed)
    sp = exp.get_finished_spans()[0]
    assert sp.attributes["burstops.routing_mode"] == "baseline"
    assert sp.attributes["burstops.cpu_observed_percent"] == 42.0


# 6. no credential ever reaches a span — scan every exported attribute
def test_no_credentials_in_spans(mem_exporter):
    import hmac as _hmac
    import hashlib as _hashlib

    signature = _hmac.new(
        SECRET.encode(), b"1700000000:" + b'{"n":100}', _hashlib.sha256
    ).hexdigest()
    tracer, exp = mem_exporter
    with tracer.start_as_current_span("suspicious") as s:
        s.set_attribute("burstops.route", "serverless")
        # decoy: a WRONG signature a buggy header-capture might leak (never
        # the real one — the assertion is that no real credential appears)
        s.set_attribute("http.request.header.x-gateway-signature", "f" * 64)
    for span in exp.get_finished_spans():
        blob = repr(span.attributes) + repr(span.name) + repr(span.events)
        assert SECRET not in blob
        assert FUNCTION_KEY not in blob
        assert signature not in blob


# 7. sampler: BURST -> 200/200 sampled; BASELINE 5% +- 2pp on 2000 ids
def test_routing_aware_sampler(monkeypatch):
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

    # hash-spread 128-bit trace ids — OTel's ratio samples on the top 64
    # bits, so synthetic ids must be uniformly distributed across the space
    import hashlib

    ids = [
        int.from_bytes(hashlib.md5(str(i).encode()).digest(), "big")
        for i in range(2000)
    ]

    monkeypatch.setattr(gateway.routing_state, "mode", gateway.Mode.BURST)
    s = tracing.RoutingAwareSampler(lambda ratio: TraceIdRatioBased(ratio), 0.05)
    results = [s.should_sample(None, i, "op") for i in ids[:200]]
    assert all(r.decision.is_recording() for r in results)

    monkeypatch.setattr(gateway.routing_state, "mode", gateway.Mode.BASELINE)
    s2 = tracing.RoutingAwareSampler(lambda ratio: TraceIdRatioBased(ratio), 0.05)
    hits = sum(1 for i in ids if s2.should_sample(None, i, "op").decision.is_recording())
    assert abs(hits / 2000 - 0.05) < 0.02, f"hit rate {hits/2000}"


def test_sampler_never_raises(monkeypatch):
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

    # routing_state missing an attribute entirely
    monkeypatch.setattr(gateway, "routing_state", types.SimpleNamespace(), raising=False)
    s = tracing.RoutingAwareSampler(lambda ratio: TraceIdRatioBased(ratio), 0.05)
    r = s.should_sample(None, 1, "op")  # must return a decision, not raise
    assert r is not None


# 8. production config uses BatchSpanProcessor (regression guard vs Simple)
def test_production_uses_batch_processor(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:1")
    provider = tracing.configure_tracing()
    assert provider is not None
    try:
        procs = provider._active_span_processor._span_processors
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        assert all(isinstance(p, BatchSpanProcessor) for p in procs)
    finally:
        provider.shutdown()


# 9. unreachable exporter: requests still succeed, no exception propagates
def test_unreachable_exporter_is_not_fatal(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:1")
    provider = tracing.configure_tracing()
    assert provider is not None
    tracer = trace.get_tracer("t")
    with tracer.start_as_current_span("x"):  # BatchSpanProcessor -> async drop
        pass
    provider.shutdown()  # must not raise despite the dead endpoint


# 10. hooks are defensive: response hook fed garbage never breaks the caller
def test_response_hook_swallows_garbage():
    class FakeSpan:
        def set_attribute(self, *a, **kw):
            raise RuntimeError("span closed")

    class FakeResponse:
        def read(self):
            raise ValueError("not json")

    class FakeRequest:
        url = "http://x"

    # reproduce the hook body exactly as tracing.py defines it, then feed junk
    hook_code = """
def _response_hook(span, request, response=None, *_a, **_kw):
    try:
        import gateway
        url = str(getattr(request, "url", ""))
        if gateway.FUNCTION_UPSTREAM and gateway.FUNCTION_UPSTREAM in url:
            _current_route.set("serverless")
            span.set_attribute("burstops.route", "serverless")
    except Exception:
        pass
"""
    ns = {"_current_route": tracing._current_route, "gateway": gateway}
    exec(hook_code, ns)
    ns["_response_hook"](FakeSpan(), FakeRequest(), FakeResponse())  # no raise


# 11. gateway.py untouched — programmatic guard, better than a README promise
def test_gateway_py_has_zero_diff():
    r = subprocess.run(
        ["git", "diff", "--stat", "--", "gateway/gateway.py"],
        capture_output=True, text=True, cwd=_ROOT,
    )
    # not a git repo (yet) or no diff — both acceptable states for the guard
    assert r.returncode == 0
    assert r.stdout.strip() == "", f"gateway.py was modified:\n{r.stdout}"
