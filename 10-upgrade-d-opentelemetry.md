# PROMPT 10 — Upgrade D: OpenTelemetry distributed tracing

> Paste this entire file to the coding agent as its task. It is self-contained.

## Your role

You are working on **BurstOps**, a Layer-7 gateway that compensates for
Kubernetes HPA provisioning lag. It routes `/calculate` either to a Kubernetes
backend or, while cluster CPU is saturated, to an HMAC-signed Azure Function. It
already exposes six `gateway_*` Prometheus metrics and a Grafana dashboard.

Metrics tell you *how many* and *how long* in aggregate. They cannot tell you why one
specific slow request was slow. This task adds distributed tracing so a single trace
shows the routing decision, which upstream was chosen, and where the milliseconds
went — including across the boundary into Azure.

## 1. The design constraint that shapes everything

`gateway/gateway.py` is the project's spec file. **This upgrade must not modify it at
all** — `git diff --stat` should show zero changes to `gateway.py` when you are done.
(Upgrades A and C do add to `gateway.py`. If either has landed, commit it first so the
diff you check here reflects only your own work.)

That is achievable because `gateway/gateway_entrypoint.py` already exists as a shim
that imports `gateway.py` and reconfigures it from the environment. Instrumentation
goes there:

```python
# gateway_entrypoint.py, after importing gateway and patching its constants
from tracing import configure_tracing, install_instrumentation
configure_tracing()                       # provider, sampler, exporter, resource
install_instrumentation(gateway.app)      # FastAPI + httpx auto-instrumentation
app = gateway.app
```

`FastAPIInstrumentor.instrument_app(app)` and `HTTPXClientInstrumentor().instrument()`
attach from outside, so no decorator, no import, and no line of `gateway.py` changes.
If you reach a point where an attribute genuinely cannot be set without editing
`gateway.py`, **stop and ask** (§8) rather than editing it.

## 2. Trace propagation, and why it does not break the HMAC contract

Use **W3C Trace Context** — the `traceparent` / `tracestate` headers — which is the
OTel default propagator, so you get it without configuration.

The question everyone asks first: does adding a header break the signature? **No.**
The gateway signs `f"{timestamp}:".encode() + body` and nothing else. Headers are
outside the signed payload, so `traceparent` rides along freely, and the Function's
`hmac_util.verify_request` never sees it. Do not touch `sign_request`,
`compute_signature`, or the three `x-gateway-*` / `x-functions-key` headers.

The flip side, worth one line in the docs: because trace headers are unsigned, a
caller can inject an arbitrary `traceparent` and graft its spans onto your traces.
For an internal demo that is fine. Note it; do not build header authentication.

## 3. Scope

```
gateway/
├── tracing.py                  # new — provider, sampler, exporter, hooks
├── gateway_entrypoint.py       # instrumentation wired in here
├── requirements.txt            # + OTel packages
└── gateway.py                  # ZERO changes
k8s/
└── gateway-deployment.yaml     # OTEL_* env vars
tests/
└── test_tracing.py             # new, uses InMemorySpanExporter
docker-compose.tracing.yml      # new overlay adding Jaeger — do not edit docker-compose.yml
docs/
└── upgrade-d-tracing.md        # backends, sampling, overhead measurements
```

Do not modify `.env`, `docker-compose.yml`, `dummy-serverless/`, `k8s/backend-*.yaml`,
or any existing test file. **Do not add OpenTelemetry packages to
`azure-function/requirements.txt`** without asking — Phase 4 deliberately kept that
file to a single dependency because every extra wheel lengthens cold start, which is
the exact latency this project measures.

## 4. Verify before you write anything

```bash
cat gateway/gateway_entrypoint.py
cat gateway/requirements.txt
grep -n -E 'httpx|AsyncClient|Client\(' gateway/gateway.py
grep -n -B3 -A 30 'async def calculate' gateway/gateway.py
grep -n -E 'K8S_UPSTREAM|FUNCTION_UPSTREAM|"source"|source=' gateway/gateway.py
grep -n -E 'app = FastAPI|@app\.' gateway/gateway.py
python -c "import opentelemetry" 2>&1 | head -1
pytest tests/ -q
```

Report: the exact way `gateway.py` constructs its HTTP client (a module-level
`httpx.AsyncClient` versus one per request — this decides whether
`HTTPXClientInstrumentor().instrument()` global patching is enough or whether you need
`instrument_client(client)` on a specific instance), the exact shape of the
`/calculate` response body, the current `requirements.txt`, and a green
`pytest tests/ -q` **before** you touch anything.

If the client is created at import time in `gateway.py`, note that
`gateway_entrypoint.py` imports `gateway` *before* calling `install_instrumentation`,
so global patching happens after the client exists. `HTTPXClientInstrumentor` handles
this by patching the transport classes, but verify empirically with the §7 test rather
than assuming — this is the single most likely thing to silently produce no client
spans.

## 5. Choosing a backend — and why the exporter is env-switched

Three plausible destinations, with the cost-minimizing choice called out:

| Backend | Cost | Sees the Function too? |
|---|---|---|
| **Jaeger all-in-one**, in-cluster / in Compose | free, memory storage, nothing persisted | no |
| **Grafana Tempo** | free, but another pod and a config file | no |
| **Application Insights** — already provisioned by Phase 5 | ingestion-billed, capped at 0.5 GB/day by Phase 5 | **yes** |

Application Insights is the interesting one: the Azure Function already reports there,
so it is the only option where one view shows both sides of the deflection. It also
adds no new infrastructure, which matters on a `Standard_B2s` node.

The catch, and state it plainly in the docs: **App Insights does not ingest raw OTLP.**
You need either the in-process `azure-monitor-opentelemetry-exporter` package, or an
OpenTelemetry Collector with the Azure Monitor exporter. Do not run a Collector — it is
another pod for no benefit at this scale. Use the in-process exporter.

So implement **one** instrumentation path and switch only the exporter:

```
OTEL_TRACES_EXPORTER = none | console | otlp | azure_monitor
```

- **`none` is the default.** Tracing must be strictly opt-in. A fresh clone with no
  `OTEL_*` env vars set behaves exactly as it does today, and §7's test asserts this.
- `otlp` for local Compose → Jaeger (which accepts OTLP natively on 4317/4318).
- `azure_monitor` for AKS → reads `APPLICATIONINSIGHTS_CONNECTION_STRING`, which
  Phase 5 already emits as a Terraform output.
- `console` for debugging without any backend at all.

Unknown value: log a warning and fall back to `none`. Never raise — a typo in an env
var must not stop the gateway from serving traffic.

### 5a. Use `BatchSpanProcessor`, never `SimpleSpanProcessor`

`SimpleSpanProcessor` exports each span synchronously as it ends, so the exporter's
network latency lands inside the request the gateway is trying to measure. On a project
whose entire subject is p95 latency, that is self-defeating. `BatchSpanProcessor`
buffers and flushes on a background thread.

Set `OTEL_BSP_SCHEDULE_DELAY=5000` and leave the queue defaults alone. Register an
atexit / lifespan shutdown that calls `provider.shutdown()` so the final batch flushes
instead of being dropped when the pod terminates.

### 5b. Sampling driven by the routing decision

Head sampling at a flat ratio is the wrong shape here. The traces you care about are
exactly the rare ones — requests deflected during a burst — and a flat 10% sampler
throws away 90% of them while faithfully recording thousands of boring baseline
requests.

The gateway already knows its mode *before* it handles a request, because
`RoutingState` is in memory. So a sampler can consult it:

```python
class RoutingAwareSampler(Sampler):
    """100% of burst-window traffic, a small fraction of baseline traffic."""
    def should_sample(self, parent_context, trace_id, name, *a, **kw):
        try:
            hot = gateway.routing_state.mode is gateway.Mode.BURST
        except Exception:
            hot = False                      # never let the sampler raise
        ratio = 1.0 if hot else BASELINE_SAMPLE_RATIO
        return self._delegate(ratio).should_sample(parent_context, trace_id, name, *a, **kw)
```

Wrap it in `ParentBased(...)` so an inbound `traceparent` that is already marked
sampled is honoured, and delegate the actual ratio decision to `TraceIdRatioBased` so
the trace-id-based determinism is preserved — do not roll your own `random()` here, or
a sampled trace can produce unsampled child spans in a different process.

`BASELINE_SAMPLE_RATIO` defaults to `0.05` via `OTEL_BASELINE_SAMPLE_RATIO`. With
App Insights' 0.5 GB/day cap, 5% of baseline plus 100% of bursts is comfortably inside
the cap at demo volumes; say what you calculated in the docs.

The sampler must **never** raise and must not touch Redis, Prometheus, or any I/O. It
runs on every single request, before the handler.

## 6. Span attributes — the part that makes the trace worth opening

Let auto-instrumentation own the HTTP semantic conventions (`http.request.method`,
`url.path`, `http.response.status_code`). Do not duplicate them under your own names.
Add only what is specific to this system, all under a `burstops.` prefix:

| Attribute | Span | Source |
|---|---|---|
| `burstops.routing_mode` | server | `routing_state.mode.value` |
| `burstops.route` | server + client | `k8s` or `serverless` |
| `burstops.cpu_observed_percent` | server | `routing_state.cpu_observed` |
| `burstops.deflect_ratio` | server | Upgrade A, if present |
| `burstops.is_leader` | server | Upgrade B, if present |
| `burstops.cost_usd` | server | Upgrade C, if present |
| `burstops.cold_start` | client | Function response body |
| `burstops.function_instance_id` | client | Function response body |

Guard every optional one with `getattr(gateway, "...", None)` so this upgrade works
whether or not A, B and C have landed. Skip the attribute when the value is `None`;
do not write the string `"None"`.

### 6a. Getting `burstops.route` without editing `gateway.py`

The routing decision happens inside `gateway.py`, which you may not touch. Two hooks
get you the attribute anyway:

1. **A `response_hook` on the httpx instrumentation.** The hook receives the request,
   so match its URL against `gateway.K8S_UPSTREAM` / `gateway.FUNCTION_UPSTREAM` and
   set `burstops.route` on the client span. If it is the Function, parse the response
   body for `cold_start` / `instance_id` and attach those too. Wrap the whole hook in
   `try/except` and swallow everything — a hook that raises inside the client call
   would turn an observability feature into an outage.
2. **A `contextvars.ContextVar` to lift it to the server span.** The hook sets the var;
   a small ASGI middleware installed from the shim reads it after `call_next` returns
   and copies the value onto the server span, along with mode, CPU and ratio (all
   readable from module state, no `gateway.py` change needed).

Add the middleware with `app.add_middleware(...)` from `gateway_entrypoint.py`. Note
that FastAPI forbids adding middleware after startup, so add it before uvicorn runs —
which the shim does naturally, since it builds `app` at import time.

### 6b. Never put credentials in a span

This is a hard rule, not a style preference. The gateway sends `x-functions-key` and
`x-gateway-signature` on every deflected request. OTel's httpx instrumentation does
**not** capture headers by default, but it will if
`OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_CLIENT_REQUEST` is set. Do not set it, do
not add it to any deployment manifest, and do not set the server-side equivalent
either. Exporting the function key to a tracing backend is a credential leak into a
system with an entirely different access-control model.

§7's test asserts this by scanning every exported attribute value for the secret.

### 6c. The Azure Function side — correlate, don't instrument

Application Insights' Python worker already reads `traceparent` on HTTP triggers and
files the invocation under the same `operation_Id`. So with **zero changes to
`azure-function/`**, the App Insights end-to-end transaction view joins the gateway's
trace to the Function's own request telemetry, dependencies and cold-start log lines.

That is the cost-minimizing answer and it is what you should ship. Verify it rather
than assume it: after a deflected request, query App Insights for the gateway's trace
id and confirm the Function's `requests` row appears under the same operation.

Adding `azure-monitor-opentelemetry` to the Function to emit real OTel spans is the
richer option, and it is explicitly **stop and ask** (§9): it contradicts Phase 4's
single-dependency rule and lengthens the cold start this project exists to measure.

### 6d. Resource attributes

```python
Resource.create({
    "service.name":        os.getenv("OTEL_SERVICE_NAME", "burstops-gateway"),
    "service.version":     os.getenv("IMAGE_TAG", "dev"),
    "deployment.environment": os.getenv("DEPLOY_ENV", "local"),
    "service.instance.id": os.getenv("HOSTNAME", socket.gethostname()),
})
```

`service.instance.id` from `HOSTNAME` gives you the pod name for free under Kubernetes,
which is what you need once Upgrade B runs three replicas — otherwise every trace looks
like it came from the same process and leader-election behaviour is invisible.

## 7. `tests/test_tracing.py` — new file

Use `InMemorySpanExporter` with a `SimpleSpanProcessor` **in tests only** so assertions
are synchronous. Match the existing suites' style: stub third-party modules, inject
time, no sleeping, no network.

Required cases:

1. **Opt-in by default.** With no `OTEL_*` env vars, `configure_tracing()` installs no
   exporter, `install_instrumentation()` is a no-op or harmless, requests succeed, and
   zero spans are produced. This is the test that proves the upgrade cannot break the
   existing system.
2. **Span shape.** One `/calculate` request produces exactly one server span and one
   client span, and the client span's parent is the server span.
3. **Propagation in.** A request carrying
   `traceparent: 00-<32 hex>-<16 hex>-01` produces spans whose trace id equals the
   supplied one. Assert the hex value, not just "some trace id".
4. **Propagation out.** The outbound request to the Function carries a `traceparent`
   header, **and** still carries all three of `x-functions-key`,
   `x-gateway-timestamp`, `x-gateway-signature` with the signature byte-identical to
   what the pre-tracing code produced. Use the project's golden vector:
   `secret="test-secret"`, `ts="1700000000"`, `body=b'{"n":100}'` →
   `0bd99a3457b14815fed94d47656212f1a92580d93f8806cf86e67f87642a022b`.
   This is the test that pins §2's claim that headers are outside the signed payload.

5. **Attributes, both modes.** In `BASELINE`, the server span has
   `burstops.routing_mode == "baseline"` and `burstops.route == "k8s"`. In `BURST`,
   `"burst"` and `"serverless"`. Assert the CPU attribute matches the state's value.
6. **No credential ever reaches a span.** Scan every attribute key and value of every
   exported span — server and client — for the HMAC secret, the function key, and the
   computed signature. Assert none appears, as a substring, anywhere:

   ```python
   for span in exporter.get_finished_spans():
       blob = repr(span.attributes) + repr(span.name) + repr(span.events)
       assert SECRET not in blob
       assert FUNCTION_KEY not in blob
       assert signature not in blob
   ```

   Keep this test even if it looks paranoid. It is the test that catches someone later
   turning on header capture "just to debug something".
7. **Sampler.** With mode forced to `BURST`, 200 requests yield 200 sampled traces.
   With mode `BASELINE` and `BASELINE_SAMPLE_RATIO = 0.05`, a fixed set of 2,000
   deterministic trace ids yields 5% ± 2 percentage points. Also assert the sampler
   returns a decision rather than raising when `routing_state` is missing an attribute.
8. **`BatchSpanProcessor` in production config.** Assert that the processor installed
   by `configure_tracing()` for the `otlp` and `azure_monitor` exporters is a
   `BatchSpanProcessor`. A regression to `SimpleSpanProcessor` would put exporter
   latency in the request path, and this is the cheapest way to prevent it.
9. **Unreachable exporter.** Point OTLP at a closed port. Requests still return 200,
   no exception propagates, and the test completes without waiting on a network
   timeout.
10. **Hooks are defensive.** Force the response hook to raise internally (feed it a
    non-JSON body) and assert the request still succeeds and the span is still exported.
11. **`gateway.py` untouched.** Assert programmatically, not by eye:
    `subprocess.run(["git","diff","--stat","--","gateway/gateway.py"])` produces empty
    output. A test is a better guard than a promise in a README.
12. All earlier test files still pass, unmodified.

## 8. Acceptance

### 8a. Local, with Jaeger

`docker-compose.tracing.yml` adds one service and sets the gateway's exporter env vars.
Do not edit `docker-compose.yml`.

```yaml
services:
  jaeger:
    image: jaegertracing/all-in-one:1.60
    ports: ["16686:16686", "4317:4317"]      # UI, OTLP gRPC
    environment: { COLLECTOR_OTLP_ENABLED: "true" }
  gateway:
    environment:
      OTEL_TRACES_EXPORTER: otlp
      OTEL_EXPORTER_OTLP_ENDPOINT: http://jaeger:4317
      OTEL_SERVICE_NAME: burstops-gateway
      OTEL_BASELINE_SAMPLE_RATIO: "1.0"      # local only — see everything
```

```bash
pytest tests/ -q
docker compose -f docker-compose.yml -f docker-compose.tracing.yml up -d --build
sleep 25

# A. baseline traffic produces traces routed to k8s
for i in $(seq 1 20); do curl -s -o /dev/null localhost:8080/calculate; done
sleep 8
curl -s 'localhost:16686/api/services' | python -m json.tool

# B. one trace, inspected: expect a server span with a client child, route=k8s
TRACE=$(curl -s 'localhost:16686/api/traces?service=burstops-gateway&limit=1')
echo "$TRACE" | python -c "
import json,sys
d=json.load(sys.stdin)['data'][0]
for s in d['spans']:
    tags={t['key']:t['value'] for t in s['tags']}
    print(s['operationName'], round(s['duration']/1000,1),'ms',
          {k:v for k,v in tags.items() if k.startswith('burstops.') or k=='url.path'})
"

# C. burst traffic: the deflected request must show route=serverless
curl -sX POST 'localhost:8002/set?pct=85'; sleep 12
for i in $(seq 1 20); do curl -s -o /dev/null localhost:8080/calculate; done
sleep 8
# re-run B's inspector; expect burstops.route=serverless and burstops.cold_start present

# D. the HMAC path is provably unaffected
docker compose logs dummy-serverless --tail 40 | grep -Ei 'signature|401|403' || echo "no auth failures"
curl -s localhost:8080/calculate | python -m json.tool     # count 168, sum 76127, source serverless
curl -s localhost:8080/metrics | grep -E 'gateway_requests_routed_total'
# a rejected signature would show as a 5xx from the gateway and no serverless counter movement

# E. all six original metrics unchanged
curl -s localhost:8080/metrics | grep -E '^gateway_' | grep -v '^#' | sort

curl -sX POST 'localhost:8002/set?pct=20'
```

### 8b. Overhead — measure it, then publish the number

Observability is not free and a project about latency should say what it costs. Run the
same Locust profile three times and report p50/p95/p99 plus RPS:

```bash
# tracing off
OTEL_TRACES_EXPORTER=none          docker compose up -d --force-recreate gateway
locust -f locustfile.py --headless -u 50 -r 10 -t 60s --host http://localhost:8080

# tracing on, 10% baseline sampling
OTEL_TRACES_EXPORTER=otlp OTEL_BASELINE_SAMPLE_RATIO=0.1  # rerun
# tracing on, 100% sampling
OTEL_TRACES_EXPORTER=otlp OTEL_BASELINE_SAMPLE_RATIO=1.0  # rerun
```

Expect single-digit-percent p95 overhead at 100% sampling and near-zero at 10%. If you
measure substantially more, the likely causes are `SimpleSpanProcessor`, a synchronous
exporter, or a hook doing JSON parsing on every response. Report what you actually
measured, including if it disagrees with this expectation.

### 8c. AKS, against the real Azure Function

```bash
CS=$(cd terraform && terraform output -raw app_insights_connection_string)
kubectl -n burstops create secret generic burstops-otel \
  --from-literal=APPLICATIONINSIGHTS_CONNECTION_STRING="$CS" \
  --dry-run=client -o yaml | kubectl apply -f -
# gateway-deployment.yaml: OTEL_TRACES_EXPORTER=azure_monitor,
#   OTEL_BASELINE_SAMPLE_RATIO=0.05, connection string via secretKeyRef
kubectl -n burstops rollout restart deploy/burstops-gateway
kubectl -n burstops rollout status deploy/burstops-gateway
```

Never put the connection string in a manifest or in git — it is an ingestion key. Print
key *names* only when you show acceptance output.

Then, with a burst driven by real load rather than `cpu-sim`:

```kusto
// F. gateway and Function in one operation
requests
| where timestamp > ago(15m)
| project timestamp, name, operation_Id, operation_ParentId, cloud_RoleName, duration, success
| order by operation_Id, timestamp asc
```

Pass criteria for §8: a Jaeger trace showing a server span with a client child and
`burstops.route` set correctly in both modes; `burstops.cold_start` present on at least
one serverless span; zero signature failures throughout; all six original metric names
byte-identical; the App Insights query returning gateway and Function rows sharing one
`operation_Id` with `cloud_RoleName` distinguishing them; `pytest tests/ -q` green with
every earlier test file unmodified; and `git diff --stat` showing **zero changes to
`gateway/gateway.py`**.

## 9. Stop and ask — do not decide these yourself

- **You conclude you must edit `gateway.py`.** That is the one thing this upgrade is
  defined by. Write down the specific attribute you cannot otherwise set and wait.
- Adding OpenTelemetry packages to `azure-function/requirements.txt` (§6c). It is a
  reasonable thing to want and a deliberate trade-off against cold start.
- Enabling any `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_*` variable (§6b).
- Running an OpenTelemetry Collector, Tempo, or any additional pod on the `Standard_B2s`
  node, or provisioning any managed tracing SKU beyond the App Insights instance
  Phase 5 already created.
- Prometheus **exemplars**, which would let a Grafana latency panel link straight into a
  trace. It is the natural next step and genuinely nice, but it needs
  `--enable-feature=exemplar-storage` in Prometheus's command line and therefore a
  change to protected config. Propose the ~10 lines; do not apply them.
- Raising `OTEL_BASELINE_SAMPLE_RATIO` above `0.05` in AKS, which pushes against
  Phase 5's 0.5 GB/day cap. Show the volume arithmetic first.
- Touching `sign_request`, `compute_signature`, the `x-gateway-*` headers, `.env`,
  `docker-compose.yml`, `dummy-serverless/`, or any existing test file.
- Renaming or reordering any of the six existing metrics, or any existing Grafana panel.
  This upgrade adds no metrics and changes no dashboards.

## 10. Report back with

1. §4's verification output, including how `gateway.py` builds its HTTP client and
   whether global `HTTPXClientInstrumentor` patching actually produced client spans.
2. `gateway/tracing.py` in full, and a unified diff of `gateway_entrypoint.py`,
   `requirements.txt` and `k8s/gateway-deployment.yaml`.
3. The pinned OTel package versions you resolved to, and the image size before and
   after — these packages are not small and the number is worth knowing.
4. `pytest tests/ -q` output and the new test file in full.
5. §8a's A–E output, including one trace printed span-by-span in both baseline and
   burst, with the `burstops.*` attributes visible.
6. §8b's three latency runs as a table: p50/p95/p99 and RPS for tracing off, 10%, and
   100%. State the overhead as a percentage.
7. §8c's App Insights result showing gateway and Function under one `operation_Id`, or
   a clear statement of what did not correlate and why.
8. Your sampling arithmetic: expected spans/day at demo volume, estimated bytes, and how
   that sits against the 0.5 GB/day cap.
9. `git diff --stat`, with `gateway/gateway.py` showing **zero changed lines** — quote
   that line of the output specifically.
10. One paragraph, plainly worded, on what a trace now tells you that the six metrics
    could not. Be concrete: name a latency question you can answer from the waterfall
    and could not answer from the dashboard.

This is the last of the four upgrades. Do not start anything from Upgrades A, B or C
here; if this upgrade's optional attributes (`burstops.deflect_ratio`,
`burstops.is_leader`, `burstops.cost_usd`) find nothing to read, that is the correct
outcome — they are guarded for exactly that reason.
