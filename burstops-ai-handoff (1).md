# BurstOps — AI Engineering Handoff & Production Roadmap

**Purpose of this document:** this is the single source of truth for any AI
assistant (Claude, or otherwise) picking up work on BurstOps. It explains,
file by file, exactly what exists today, why it was built the way it was,
what is still missing, and the precise sequence of work required to take
this from a local Docker Compose prototype to a 10/10 enterprise-grade
Azure/AKS production system.

Read this entire document before writing any code. Do not skip to a later
phase — each phase depends on artifacts/conventions established in the one
before it.

---

## 0. Quick Orientation (read this first)

- **This is a local Docker Compose prototype**, not a deployed system. No
  Azure resources exist anywhere yet.
- **`docker compose up --build` does NOT currently work.** It's not just
  `dummy-serverless/` and `cpu-sim/` that are missing — `dummy-backend/`
  is also missing its `Dockerfile` and `requirements.txt`, and Grafana has
  no Prometheus datasource provisioned. See §2.6 for the full, verified
  list — this handoff has been directly checked against the actual files
  in the working copy, not just against the compose file's references.
- **`gateway/gateway.py` is the spec.** Its constants, class names, metric
  names, and thresholds are the contract every other component (dummy or
  real) must match. Don't rename anything in it casually.
- **Work one phase/gap at a time.** Wait for the user to say which phase,
  upgrade, or gap-fill they want. Don't scaffold Phase 5 while asked for
  Phase 4, and don't silently "fix" every gap in §2.6 at once unless asked
  to get the whole stack running.
- **The `README.md` in the repo is partly aspirational.** Its file tree
  lists files (`dummy-backend/Dockerfile`, `dummy-backend/requirements.txt`,
  `grafana/provisioning/datasources/prometheus.yml`) that do not exist in
  the working copy. Treat the README as a target/description of intent,
  not as proof something exists — see §2.14.

---

## 1. What BurstOps Is

BurstOps is a Layer-7 traffic gateway that compensates for Kubernetes
Horizontal Pod Autoscaler (HPA) provisioning lag. HPA typically takes
30–90+ seconds to notice a CPU spike, provision new pods, and get them
ready to serve traffic. BurstOps closes that gap by watching cluster CPU in
real time and, the moment it crosses a threshold, deflecting *overflow*
traffic to an Azure Function instead of letting the existing pods melt
under load. When CPU drops back down, traffic returns to Kubernetes.

It is **not** a replacement for HPA — it's a shock absorber that buys HPA
time to catch up.

---

## 2. Current State — What Is Actually Built

Everything below exists today, locally, as a Docker Compose stack in
`burstops-local/`. It runs entirely on a laptop with no Azure credentials —
Azure is mocked by two local FastAPI services standing in for AKS pods and
an Azure Function.

### 2.1 Repository layout (as of this handoff)

```
burstops-local/
├── docker-compose.yml
├── .env
├── README.md
├── gateway/
│   ├── gateway.py              ← core FastAPI app (READ-ONLY, see §2.2)
│   ├── gateway_entrypoint.py   ← env-var shim, patches gateway.py at boot
│   ├── Dockerfile
│   └── requirements.txt
├── dummy-backend/
│   ├── app.py                  ← stands in for an AKS pod
│   └── nginx.conf              ← VIP load balancer in front of 2 replicas
├── dummy-serverless/            ← ⚠ NOT YET BUILT — see §2.6
├── cpu-sim/                     ← ⚠ NOT YET BUILT — see §2.6
├── prometheus/
│   └── prometheus.yml
├── grafana/
│   └── provisioning/dashboards/
│       ├── burstops.json       ← 6-panel dashboard, auto-provisioned
│       └── dashboard.yml
├── locust/
│   └── locustfile.py           ← load generator
├── tests/
│   └── test_hysteresis.py      ← pytest suite, imports gateway.py directly
└── k8s/
    ├── backend-deployment.yaml ← already written, targets Phase 6
    └── backend-service.yaml    ← already written, targets Phase 6
```

Local tooling artifacts you may see when you unzip the working copy
(`.venv/`, `__pycache__/`, `.pytest_cache/`, `.cursor/`, `.DS_Store`) are
**not part of the source tree**. Ignore them; never port anything from
`.venv/` into Azure Function or AKS code.

### 2.2 `gateway/gateway.py` — the core of the system

This is a single-file FastAPI app (~215 lines). Treat it as the spec —
every later phase must stay consistent with the names, thresholds, and
metrics defined here. Do not rename anything in it without an explicit
instruction to do so.

**Config constants (currently hardcoded, patched at runtime by
`gateway_entrypoint.py` from environment variables — see §2.3):**

| Constant | Value | Meaning |
|---|---|---|
| `PROMETHEUS_URL` | `http://prometheus:9090/api/v1/query` | Prometheus query endpoint |
| `PROM_QUERY` | `avg(rate(container_cpu_usage_seconds_total{namespace="burstops"}[30s])) * 100` | The exact PromQL the poller runs every cycle |
| `POLL_INTERVAL_SECONDS` | `2` | How often the background poller queries Prometheus |
| `POLL_TIMEOUT_SECONDS` | `1.5` | HTTP timeout for each poll |
| `BURST_THRESHOLD` | `80.0` | CPU% at/above which BASELINE → BURST |
| `RECOVERY_THRESHOLD` | `60.0` | CPU% below which BURST → BASELINE |
| `STALE_STATE_GRACE_SECONDS` | `15` | How long to trust the last-known CPU reading if Prometheus goes unreachable |
| `FAIL_OPEN_TO_BURST` | `True` | After the grace period expires, fail open to BURST rather than blindly trusting K8s |
| `K8S_UPSTREAM` | (placeholder, overridden by `.env`) | Backend to call when in BASELINE mode |
| `FUNCTION_UPSTREAM` | (placeholder, overridden by `.env`) | Backend to call when in BURST mode |
| `FUNCTION_KEY` | (placeholder, overridden by `.env`) | Azure Function host key, sent as `x-functions-key` |
| `GATEWAY_HMAC_SECRET` | (placeholder, overridden by `.env`) | Shared secret for HMAC request signing |

**Prometheus self-instrumentation** (exposed at `GET /metrics`):

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `gateway_routing_mode` | Gauge | — | `0` = baseline/K8s, `1` = burst/serverless |
| `gateway_cpu_observed_percent` | Gauge | — | Last CPU% seen by the poller |
| `gateway_prometheus_poll_failures_total` | Counter | — | Failed polls against Prometheus |
| `gateway_requests_routed_total` | Counter | `route` (`k8s`\|`serverless`) | Requests routed by destination |
| `gateway_upstream_latency_seconds` | Histogram | `route` | Upstream response latency |
| `gateway_state_transitions_total` | Counter | `direction` (e.g. `baseline_to_burst`) | Every mode flip |

**`RoutingState` — the hysteresis state machine.** This is the most
important piece of logic in the whole system:

- Dual-threshold (hysteresis) design specifically to prevent flapping: it
  takes CPU ≥ 80% to enter BURST, but CPU must drop *below 60%* — not just
  below 80% — to return to BASELINE. Anything between 60–80% is a dead
  band where the mode never changes.
- `update_from_cpu(cpu_percent)` is called by the poller on every
  successful scrape.
- `apply_fail_safe()` is called on poll failure. If Prometheus has been
  unreachable for ≤15s, it keeps the current mode (tolerates transient
  blips). Past 15s, if `FAIL_OPEN_TO_BURST` is true and mode isn't already
  BURST, it force-transitions to BURST — the reasoning documented in the
  code is that overflowing to serverless is safer than routing blind
  against a cluster nobody is watching anymore.
- Every mode transition logs at INFO/ERROR and increments
  `gateway_state_transitions_total`.

**Background poller (`poll_prometheus_loop`):** runs as an asyncio task
started in the FastAPI `lifespan` context, decoupled from the request path
on purpose — a slow/failing Prometheus never blocks a live request.

**HMAC request signing (`sign_request`):** for every request forwarded to
the Function, the gateway computes:
```
timestamp = str(int(time.time()))
signature = HMAC_SHA256(GATEWAY_HMAC_SECRET, f"{timestamp}:".encode() + body).hexdigest()
```
and sends three headers: `x-functions-key`, `x-gateway-timestamp`,
`x-gateway-signature`. This is defense in depth beyond the function key
alone — timestamp + HMAC means a leaked key can't be replayed indefinitely
and the receiving side can reject stale or tampered requests. **Any real
Azure Function or dummy-serverless implementation must reproduce this
exact signing scheme byte-for-byte** (same header names, same
`f"{timestamp}:"` prefix convention, same hex digest), or requests will be
rejected.

**Routes exposed by the gateway:**

| Route | Methods | Behavior |
|---|---|---|
| `/calculate` | GET, POST | Proxies to `K8S_UPSTREAM` or `FUNCTION_UPSTREAM` depending on current `RoutingState.mode`; times the call in `gateway_upstream_latency_seconds`; increments `gateway_requests_routed_total` |
| `/metrics` | GET | Prometheus scrape endpoint |
| `/health` | GET | Returns `{"mode": ..., "last_cpu": ...}` |

### 2.3 `gateway/gateway_entrypoint.py`

A deliberate design choice: `gateway.py` is treated as read-only "spec"
source. Rather than editing it to read env vars directly, this shim
imports it, patches its module-level constants (`K8S_UPSTREAM`,
`FUNCTION_UPSTREAM`, `FUNCTION_KEY`, `GATEWAY_HMAC_SECRET`,
`PROMETHEUS_URL`) from environment variables at process startup, then
launches uvicorn against `gateway:app`. Preserve this pattern in future
phases — don't collapse the two files into one, and don't have Terraform
or Kubernetes manifests try to bypass the shim by setting different env
var names.

### 2.4 `gateway/Dockerfile`

Build context is `./gateway`. Installs `requirements.txt`
(`fastapi==0.115.5`, `uvicorn[standard]==0.32.1`, `httpx==0.28.1`,
`prometheus-client==0.21.1`), copies `gateway.py` and
`gateway_entrypoint.py` in unmodified, exposes port `8080`, and runs
`python gateway_entrypoint.py`. **`gateway.py` must physically live inside
`gateway/`** — the build will fail if it's anywhere else, since the
Dockerfile's `COPY gateway.py .` only sees files inside the build context.

### 2.5 `dummy-backend/` — stand-in for AKS pods

- `app.py`: FastAPI app with three endpoints:
  - `GET/POST /calculate` — runs a real prime sieve up to 1000 (cheap CPU
    work, produces a JSON payload with `source: "k8s"`, hostname, prime
    count, and sum). Exists to generate genuine, non-trivial CPU work that
    cAdvisor can measure.
  - `POST /burn-cpu?ms=<int>` (1–30000, default 500) — busy-loops doing
    floating-point arithmetic the CPU can't optimize away, for exactly
    `ms` milliseconds. This is the deterministic knob for demos: organic
    traffic alone may not reliably saturate a 1.0-CPU-capped container, so
    `/burn-cpu` gives a reliable way to cross the 80% threshold on demand.
  - `GET /health` — liveness probe.
- `nginx.conf`: a VIP (`http://dummy-backend:8000`) round-robining across
  `dummy-backend-1:8000` and `dummy-backend-2:8000`, simulating a K8s
  Service load-balancing across pod replicas.

In `docker-compose.yml`, both dummy-backend replicas are capped at
`cpus: "1.0"` deliberately — the code comment explains that
`gateway.py`'s query measures `rate(...)*100`, i.e. cores × 100 (not %-of-
quota), so a smaller CPU cap (e.g. 0.3) could never numerically reach the
80 threshold.

### 2.6 Known gaps — do not assume these exist

This section has been verified directly against the actual files in the
working copy (not inferred from `docker-compose.yml` references alone).
**Four** things are missing, not two:

- **`dummy-serverless/`** — referenced by `docker-compose.yml` (the
  `dummy-serverless` service, built from `./dummy-serverless`), by `.env`
  (`FUNCTION_UPSTREAM=http://dummy-serverless:8001/calculate`), and by the
  README's architecture diagram. It is supposed to validate
  `x-functions-key`, `x-gateway-timestamp`, and `x-gateway-signature`
  exactly as `gateway.py` generates them, and inject 50–150ms of
  artificial latency to simulate a cold-ish Azure Function, listening on
  port `8001` (that's the port baked into `FUNCTION_UPSTREAM` and into
  the README's service map). **The directory does not exist in the
  current tree — confirmed empty.**

- **`cpu-sim/`** — referenced by `docker-compose.yml` (built from
  `./cpu-sim`, port `8002`, env var `INITIAL_CPU_PCT`) and by
  `prometheus/prometheus.yml` (job `cpu-sim`, scraped at
  `cpu-sim:8002/metrics`). Its purpose per the compose file's own
  comments: Docker Desktop's cAdvisor runs in restricted mode and only
  exposes aggregate `/`, `/docker`, `/restricted` metrics — never
  per-container ones — so `cpu-sim` is meant to artificially publish
  `container_cpu_usage_seconds_total` in the same shape `gateway.py`'s
  PromQL expects, with `ramp-up`/`ramp-down` control endpoints implied by
  the compose comment (`curl -X POST http://localhost:8002/ramp-up`).
  **The directory does not exist in the current tree — confirmed empty.**

- **`dummy-backend/Dockerfile` and `dummy-backend/requirements.txt`** —
  ⚠ **newly identified, not previously flagged in any prior handoff.**
  `dummy-backend/` currently contains only `app.py` and `nginx.conf`.
  `docker-compose.yml` declares `dummy-backend-1` and `dummy-backend-2`
  with `build: context: ./dummy-backend`, which requires a `Dockerfile`
  in that directory — **there isn't one.** There's also no
  `requirements.txt` to install FastAPI/uvicorn into that image. This
  means the *core* dummy K8s backend — not just the serverless/cpu-sim
  mocks — currently fails to build too. The README's file tree names both
  files as if they exist; they don't. When building this, mirror the
  `gateway/Dockerfile` pattern (§2.4): `python:3.12-slim`, install
  `requirements.txt` first for layer caching, copy `app.py` in, expose
  `8000`, run uvicorn against `app:app` on `0.0.0.0:8000`. Minimal
  requirements are `fastapi` + `uvicorn[standard]` (no `httpx` or
  `prometheus-client` needed — `app.py` doesn't import them).

- **`grafana/provisioning/datasources/`** — ⚠ **newly identified.** The
  provisioned dashboard (`grafana/provisioning/dashboards/burstops.json`)
  has every panel hardcoded to `"datasource": {"uid": "burstops-prometheus"}`,
  but there is no datasource-provisioning YAML anywhere in the repo that
  creates a Grafana datasource with that UID. `dashboard.yml` only
  provisions the *dashboard* (the panel layout), not the *datasource* it
  points at. Without this file, Grafana will load the dashboard but every
  panel will show a "datasource not found" error until someone manually
  creates a Prometheus datasource in the Grafana UI with UID
  `burstops-prometheus` pointed at `http://prometheus:9090`. The README's
  file tree lists `grafana/provisioning/datasources/prometheus.yml` as if
  it exists; it doesn't. Fixing this is a small, low-risk addition (a
  single `datasources/prometheus.yml` with `apiVersion: 1`, one Prometheus
  datasource entry, `uid: burstops-prometheus`, `url:
  http://prometheus:9090`, `isDefault: true`) — see §2.14 for why this
  wasn't caught earlier.

**As it stands, `docker compose up --build` will fail** on three of the
nine services (`dummy-backend-1`, `dummy-backend-2`, `dummy-serverless`,
`cpu-sim` — four service *instances*, two missing directories plus one
directory missing its build files), and even once it builds, the Grafana
dashboard will render with broken panels until the datasource gap is also
closed. Building `dummy-serverless/` and `cpu-sim/`, adding
`dummy-backend/`'s missing build files, and adding the Grafana datasource
file are the actual next step, ahead of Phase 4 below (Phase 4 literally
replaces `dummy-serverless/`, so `dummy-serverless/` must exist first for
its HMAC-validation logic to be ported out of).

### 2.7 `prometheus/prometheus.yml`

Four scrape jobs, `scrape_interval: 2s` globally:

1. **`cadvisor`** — scrapes `cadvisor:8080`. Uses `metric_relabel_configs`
   to stamp `namespace="burstops"` only on the two dummy-backend replicas
   (matched by container `name` regex `.*/?burstops-backend-[12]$`, with a
   fallback match on
   `container_label_com_docker_compose_service`), and keeps only
   `container_cpu_usage_seconds_total`, `container_memory_usage_bytes`,
   and `container_spec_cpu_quota`. The comment explains why: averaging CPU
   across the *whole* Compose stack (Grafana, Locust, Prometheus itself,
   etc.) would dilute the reading so far that the 80% burst line could
   never be crossed.
2. **`burstops-gateway`** — scrapes `gateway:8080/metrics` for all
   `gateway_*` metrics.
3. **`cpu-sim`** — scrapes `cpu-sim:8002/metrics` (⚠ target doesn't exist
   yet, see §2.6).
4. **`prometheus`** — self-scrape.

### 2.8 `grafana/provisioning/dashboards/burstops.json`

Auto-provisioned dashboard, **"BurstOps — Burst Routing Monitor"**, with 6
panels: *Routing Mode*, *CPU Observed vs Thresholds*, *Requests Routed by
Destination*, *Upstream Latency p95*, *State Transitions*, *Prometheus
Poll Failures*. These panel names map directly to the metrics in §2.2 —
keep that mapping intact if the dashboard is ever edited or extended (e.g.
Upgrade C's cost metric should become a 7th panel, not a replacement for
an existing one).

### 2.9 `locust/locustfile.py`

`BurstOpsUser` mixes two weighted tasks against `BACKEND_URL` (default
`http://dummy-backend:8000`, but note the compose command actually points
Locust's `--host` at `http://gateway:8080`):

- **95%**: `GET /calculate` — organic traffic through the gateway.
- **5%**: `POST /burn-cpu?ms=<1500|2000|2500>` — sent **directly to the
  dummy-backend VIP**, not through the gateway (the gateway only proxies
  `/calculate`), so cAdvisor sees real CPU load on the backend replicas.

Wait time between tasks: 0.5–1.5s. Prints a helpful banner on test start
pointing at Grafana, a manual burst-trigger curl command, and the health
endpoint.

### 2.10 `tests/test_hysteresis.py`

A dependency-free pytest suite (~sub-second runtime) that imports
`RoutingState` and `Mode` directly from `gateway.py` — zero HTTP calls,
zero Docker required. It stubs out `fastapi`, `httpx`, and
`prometheus_client` at the module level (since `gateway.py` imports them
at import time) with minimal fakes, so the test process never needs the
full runtime installed. It asserts six invariants:

1. Threshold crossing: BASELINE → BURST exactly at 80%.
2. Hysteresis band: no flip anywhere between 60–80%.
3. Recovery: BURST → BASELINE only below 60%.
4. No-flapping guarantee under oscillation inside the band.
5. Fail-safe grace period: stale data tolerated for 15s.
6. Fail-open behavior: after the grace period, mode forces to BURST.

**Any change to `RoutingState`'s thresholds or fail-safe logic must keep
this test file passing, or be updated alongside it in the same change.**

### 2.11 `k8s/` — already partially built, ahead of Phase 6

Two manifests exist already, written in anticipation of Phase 6:

- **`backend-deployment.yaml`** — `Deployment` named `burstops-backend` in
  namespace `burstops`, 2 replicas, image placeholder
  `burstopsacr.azurecr.io/burstops-backend:v1`, resource requests
  `250m`/`128Mi`, limits `1000m`/`256Mi` (explicitly matched to the
  `cpus: "1.0"` Compose cap — see §2.5), liveness/readiness probes against
  `GET /health` on port 8000. Pod template carries label
  `burstops-namespace: burstops`, called out in a comment as exactly what
  Prometheus's relabel rules (§2.7) are expected to match once running in
  AKS.
- **`backend-service.yaml`** — `LoadBalancer` Service `burstops-backend`
  in namespace `burstops`, port 8000 → targetPort 8000.

**Phase 6 should extend this folder** (add `gateway-deployment.yaml` and
`ingress.yaml`), not recreate what's already there. Keep the same
namespace (`burstops`) and the same `burstops-namespace: burstops` label
convention so Prometheus relabeling continues to work unchanged in AKS.

### 2.12 `docker-compose.yml` service map

| Service | Image/Build | Port | Notes |
|---|---|---|---|
| `dummy-backend-1`, `dummy-backend-2` | build `./dummy-backend` | — | `cpus: "1.0"`, `mem_limit: 128m` each |
| `dummy-backend` | `nginx:1.27-alpine` | `8000` | VIP in front of the two replicas |
| `dummy-serverless` | build `./dummy-serverless` | — | ⚠ missing, see §2.6 |
| `cpu-sim` | build `./cpu-sim` | `8002` | ⚠ missing, see §2.6 |
| `gateway` | build `./gateway` | `8080` | depends on backend, serverless, prometheus, cpu-sim |
| `cadvisor` | `gcr.io/cadvisor/cadvisor:v0.49.1` | `8082` | privileged, mounts host `/`, docker socket, `/sys` |
| `prometheus` | `prom/prometheus:v2.53.1` | `9090` | 24h retention, `--web.enable-lifecycle` |
| `grafana` | `grafana/grafana:11.1.4` | `3000` | admin/burstops by default (from `.env`) |
| `locust` | `locustio/locust:2.29.1` | `8089` | targets `http://gateway:8080`, does not auto-start the test |

### 2.13 `.env`

```
K8S_UPSTREAM=http://20.219.208.79:8000
FUNCTION_UPSTREAM=http://dummy-serverless:8001/calculate
GATEWAY_HMAC_SECRET=local-dev-secret-change-in-prod
FUNCTION_KEY=local-dev-function-key
PROMETHEUS_URL=http://prometheus:9090/api/v1/query
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=burstops
```
Note `K8S_UPSTREAM` currently points at a bare IP (`20.219.208.79:8000`)
rather than the `dummy-backend` service name — worth flagging to the user,
since inside the Compose network `http://dummy-backend:8000` is the
correct, portable target; a hardcoded IP will break if that container is
ever rebuilt or moved. Don't change it silently — confirm with the user
first, since it may be intentional (e.g. testing against a real remote
box). Note also that `docker-compose.yml`'s own inline default for this
same var (`K8S_UPSTREAM: ${K8S_UPSTREAM:-http://dummy-backend:8000}`) is
the *portable* value — the mismatch only matters when `.env` is present
and loaded, which it is by default with `docker compose`.

### 2.14 Documentation vs. reality — what to trust

Two documents already exist describing this project (a prior "source of
truth" doc and an earlier draft of this handoff). Both were written by
reasoning over `docker-compose.yml`, `.env`, and the README rather than by
opening every file in the working copy, so both **understated** the gap
list in §2.6 — they caught the two gaps `docker-compose.yml` explicitly
depends on (`dummy-serverless/`, `cpu-sim/`) but missed two more subtle
ones that only show up by actually listing `dummy-backend/`'s contents
and reading the dashboard JSON's datasource references:

- `dummy-backend/` is missing `Dockerfile` and `requirements.txt`.
- `grafana/provisioning/` has no `datasources/` subfolder, so the
  dashboard's `burstops-prometheus` datasource UID resolves to nothing.

The **README's file tree section is describing the intended final state
of the repo, not its current contents** — it lists files for
`dummy-backend/Dockerfile`, `dummy-backend/requirements.txt`, and
`grafana/provisioning/datasources/prometheus.yml` that don't exist. This
isn't malicious or even necessarily wrong — READMEs often get written
slightly ahead of the code — but it means **the README is not a reliable
inventory of what's actually in the repo**. When in doubt about whether a
file exists, check the working copy directly (`find`/`ls`), don't infer
existence from what `docker-compose.yml`, `.env`, or `README.md` merely
*reference*. This handoff document (§2 as a whole) has been verified this
way as of the version you're reading now; if the repo changes after this
handoff was written, re-verify rather than trusting this document blindly
either.

---

## 3. Production Roadmap — Phases

Execute **one phase or upgrade at a time**, only when the user asks for
that specific scope. Do not write Phase 5 and 6 code while asked for
Phase 4. Each phase below lists concrete deliverables and what "done"
looks like.

### Phase 0 (prerequisite, do first if asked to "run the stack")
Close every gap in §2.6 so `docker compose up --build` actually succeeds
and the Grafana dashboard actually renders data. This isn't in the
original phase numbering, but nothing else works without it. Concretely:

- Build `dummy-serverless/` (HMAC validation + latency injection + `app`
  Dockerfile + `requirements.txt`, listening on port `8001`).
- Build `cpu-sim/` (metrics publisher + ramp-up/ramp-down endpoints +
  Dockerfile + `requirements.txt`, listening on port `8002`).
- Add `dummy-backend/Dockerfile` and `dummy-backend/requirements.txt` (no
  existing app code needs to change — `app.py` and `nginx.conf` are
  already correct).
- Add `grafana/provisioning/datasources/prometheus.yml` provisioning a
  Prometheus datasource with `uid: burstops-prometheus` pointed at
  `http://prometheus:9090`, so the existing dashboard panels resolve.

**Acceptance:** `docker compose up --build` starts all 9 services
successfully; `curl http://localhost:8080/health` returns `{"mode":
"baseline", ...}`; hitting `POST http://localhost:8000/burn-cpu?ms=8000`
against both replicas concurrently eventually flips `mode` to `"burst"`
within a few poll cycles; Grafana's dashboard at `localhost:3000` shows
live data in every panel with no "datasource not found" errors.

### Phase 4 — Real Azure Function Implementation
Replace `dummy-serverless/` with a live Azure Function.

- Create `azure-function/`.
- `function_app.py` using the Azure Functions **V2 Python Programming
  Model**.
- Port the HMAC-SHA256 validation logic from `dummy-serverless/app.py`
  (built in Phase 0) — header names and signing scheme must match §2.2's
  `sign_request` exactly: `x-functions-key`, `x-gateway-timestamp`,
  `x-gateway-signature`, same `f"{timestamp}:"` + body signing
  convention.
- Port the prime-sieve "work" logic (mirroring `dummy-backend/app.py`'s
  `/calculate`) so the Function does comparable, real work rather than
  just echoing.

**Acceptance:** a request signed by `gateway.py`'s `sign_request()` is
accepted by the real Function when `FUNCTION_UPSTREAM` points at it; a
request with a stale timestamp or bad signature is rejected with 401/403.

### Phase 5 — Infrastructure as Code (Terraform)
- `terraform/main.tf`.
- Resources: `azurerm_resource_group`, `azurerm_kubernetes_cluster` (AKS,
  `Standard_D2s_v5` nodes), `azurerm_container_registry` (ACR),
  `azurerm_storage_account`, `azurerm_service_plan` (Consumption Plan),
  `azurerm_linux_function_app`.
- `GATEWAY_HMAC_SECRET` and `FUNCTION_KEY` must be injected via app
  settings / Key Vault references, never hardcoded in `.tf` files or
  committed state.

**Acceptance:** `terraform plan` produces a clean plan with no hardcoded
secrets in the diff; `terraform apply` stands up a resource group
containing all of the above with names/tags consistent with `burstops`
naming used elsewhere (namespace `burstops`, resource group e.g.
`rg-burstops-prod`).

### Phase 6 — AKS Migration & Ingress
- Extend `k8s/` (§2.11) — do not recreate `backend-deployment.yaml` /
  `backend-service.yaml`.
- Add `gateway-deployment.yaml` (same namespace `burstops`, env vars
  sourced from Kubernetes Secrets for `GATEWAY_HMAC_SECRET`/`FUNCTION_KEY`,
  matching the env var names `gateway_entrypoint.py` already expects — see
  §2.3).
- Add `ingress.yaml` exposing the gateway securely (TLS termination,
  appropriate class for AKS — e.g. `nginx` or AGIC depending on what
  Phase 5's Terraform provisioned).
- Define the image build/push/pull path: containerize `gateway` and
  `dummy-backend` (or its Phase-6 successor), push to the ACR from Phase
  5, reference those image paths in the deployment manifests (replacing
  the `burstopsacr.azurecr.io/burstops-backend:v1` placeholder already in
  `backend-deployment.yaml`).

**Acceptance:** `kubectl apply -f k8s/` succeeds against the AKS cluster
from Phase 5; the gateway's `/health` endpoint is reachable through the
Ingress; Prometheus (deployed however Phase 6 chooses — e.g. Azure
Monitor managed Prometheus or a self-hosted chart) shows `gateway_*`
metrics with the same names as §2.2.

### Upgrade A — Adaptive PID / Proportional Deflection
Current flaw: routing is binary. 100% deflection at the burst threshold
drops K8s CPU to ~0%, which then over-corrects back to BASELINE too
fast — causing oscillation even with hysteresis, just at a coarser
grain. Target: instead of `Mode.BASELINE`/`Mode.BURST` fully gating
`/calculate`, compute a deflection *ratio* (e.g. if target is 75% and
observed is 85%, stochastically send ~50% of traffic to serverless) so
the cluster settles into a steady saturation point rather than
bang-bang oscillating. This changes `RoutingState` from a two-value enum
to something that also tracks a continuous ratio — coordinate carefully
with `tests/test_hysteresis.py`, which will need new test cases for the
ratio logic without breaking the existing six invariants.

### Upgrade B — Distributed State Backplane (Redis)
Current flaw: `RoutingState` is a single in-memory Python object. Once
the gateway is scaled to N replicas in AKS (Phase 6), each replica polls
Prometheus and makes its own routing decision independently —
"split-brain" risk where replicas disagree mid-transition. Target: move
authoritative state to Azure Cache for Redis; elect one replica (or use a
lease/lock) to write CPU state and the resulting mode/ratio, all replicas
read it before routing each request.

### Upgrade C — FinOps Telemetry Engine
Add `Counter("gateway_estimated_cost_usd_total", ..., ["service"])` with
label values `"aks"` / `"serverless"`, incremented by a small fractional
cost estimate per request based on route. Surface this as a 7th Grafana
panel (don't touch the existing 6 — see §2.8) showing live cost/savings
of burst routing.

### Upgrade D — Distributed Tracing (OpenTelemetry)
Inject standard W3C `traceparent` headers at the gateway on every
forwarded request, and propagate/log them in both the Azure Function
(Phase 4) and the AKS backend, so a single request can be traced
end-to-end across K8s and serverless.

---

## 4. Rules for the AI Doing This Work

1. **`gateway.py`'s existing constants, class names (`RoutingState`,
   `Mode`), metric names, and thresholds are the spec.** Don't rename or
   restructure them without being explicitly asked to.
2. **HMAC consistency is non-negotiable.** `gateway.py`'s `sign_request()`
   is the reference implementation; every downstream verifier
   (`dummy-serverless`, the real Azure Function) must match it exactly —
   header names, signing input format, hash algorithm.
3. **Fill Phase 0 gaps before Phase 4.** `dummy-serverless/` and
   `cpu-sim/` don't exist yet (§2.6); Phase 4 explicitly ports logic out
   of `dummy-serverless/app.py`, so that file has to exist first.
4. **One phase at a time.** Wait for the user to specify which phase or
   upgrade to work on. Don't pre-emptively scaffold later phases.
5. **Keep `tests/test_hysteresis.py` green.** Any change to
   `RoutingState`'s behavior needs a corresponding test update in the same
   change, not a follow-up.
6. **Don't touch `k8s/backend-deployment.yaml` / `backend-service.yaml`'s
   existing conventions** (namespace `burstops`, the
   `burstops-namespace: burstops` pod label) — Phase 6 additions must stay
   consistent with them, since Prometheus's relabel rules depend on that
   label surviving into AKS.
7. **Don't silently touch `.env` values** like the hardcoded
   `K8S_UPSTREAM` IP (§2.13) — flag anything that looks like it might be
   intentional-but-fragile and ask before changing it.
8. **Ignore `.venv/`, `__pycache__/`, `.pytest_cache/`, `.cursor/`** —
   these are local tooling, not source.
9. **Verify against the working copy, not against references to it.**
   `docker-compose.yml`, `.env`, and `README.md` all *reference* files
   that may not actually exist (see §2.14) — two such gaps were missed by
   earlier documentation passes that reasoned from those files instead of
   listing the actual directories. Before claiming a file exists or
   doesn't, check the working copy directly.
