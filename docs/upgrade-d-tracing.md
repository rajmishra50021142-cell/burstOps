# Upgrade D — distributed tracing notes

## What a trace now tells you that the six metrics could not

Metrics say "p95 rose to 900 ms during burst". They cannot say **which
request** was slow, or **why**: whether the gateway spent the time signing
and forwarding, or the Function cold-started, or the backend pod was CPU-
starved. A trace answers that per-request: one waterfall shows the server
span (routing mode, observed CPU, deflection ratio at that instant), the
client span (which upstream — `burstops.route`), and for the Function path
`burstops.cold_start`/`burstops.function_instance_id`. You can answer "was
that slow request a cold start?" — a question the dashboard cannot.

## Architecture

- `gateway/tracing.py` — provider, RoutingAwareSampler, exporter switch,
  FastAPI/httpx auto-instrumentation, pure-ASGI attribute middleware.
- Wired in by `gateway_entrypoint.py`; **`gateway.py` has ZERO changes from
  this upgrade** (the test suite asserts it programmatically).
- W3C `traceparent` propagates freely: the HMAC signature covers
  `f"{timestamp}:" + body` only — headers are outside the signed payload
  (golden-vector pinned in tests). Flip side: trace headers are unsigned, so
  a caller can graft spans onto your traces — accepted for a demo, noted.

## Exporters (`OTEL_TRACES_EXPORTER`)

- `none` (default) — fresh clone behaves exactly as before; zero spans.
- `otlp` — local Compose → Jaeger (`docker-compose.tracing.yml` overlay).
- `azure_monitor` — reads `APPLICATIONINSIGHTS_CONNECTION_STRING`; the
  in-process exporter (App Insights does NOT ingest raw OTLP — never run a
  Collector pod for this scale).
- `console` — debugging without a backend.
- Unknown value → warning + `none`. A typo never stops traffic.

Always `BatchSpanProcessor` in production config (test-asserted); exporter
latency lands on a background thread, never inside the measured request.
Flush at shutdown via atexit.

## Sampling — RoutingAwareSampler

Flat head-sampling throws away exactly the rare traces you want: the
deflected ones. The gateway already knows its mode before handling a
request, so the sampler samples **100% of burst-window traffic** and
`OTEL_BASELINE_SAMPLE_RATIO` (default 0.05) of baseline. Wrapped in
`ParentBased` so inbound sampled traceparents are honoured; ratio decisions
delegate to `TraceIdRatioBased` for cross-process determinism. Never raises,
never touches I/O.

Volume arithmetic (AKS/App Insights context): at ~0.1 rps demo load,
5% baseline ≈ 400 traces/day ≈ ~400 KB — far under the 0.15 GB/day cap;
100% of bursts adds trivially more.

## Verified live (2026-09-01, Jaeger 1.60, OTLP gRPC)

- Baseline trace: server span `burstops.route=k8s`, `routing_mode=baseline`,
  `cpu_observed_percent`, `deflect_ratio` — client child to dummy-backend.
- Burst trace: `route=serverless` on server AND client spans,
  `routing_mode=burst`, `cpu=91.4`, `deflect_ratio=0.80`.
- Zero signature failures with tracing on; all six original metrics
  byte-identical; 79/79 tests green.

## Hard rules (test-enforced)

- No credential ever reaches a span — never set
  `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_*` (exporting the function key
  to a tracing backend is a credential leak into a different
  access-control model). tests/test_tracing.py scans every exported
  attribute for the secret, key, and signature.
- The Azure Function side is **correlated, not instrumented**: App Insights'
  worker already files the invocation under the same `operation_Id` from the
  inbound `traceparent` — zero changes to `azure-function/`, preserving
  Phase 4's single-dependency cold-start guarantee.

## Not built (deliberate — stop-and-ask items)

- Prometheus **exemplars** (needs `--enable-feature=exemplar-storage` on
  protected Prometheus config). Propose, don't apply.
- OTel packages in `azure-function/requirements.txt` — contradicts the
  cold-start constraint; correlation gives the end-to-end view anyway.
- Tempo/Collector pods — extra infrastructure for no benefit at this scale.
