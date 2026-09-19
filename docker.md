# Docker — the BurstOps local stack

BurstOps is a burst-traffic gateway that buys Kubernetes HPA time. Since AKS
was deliberately not used (see `docs/architecture-decision.md`), **the local
Docker Compose stack IS the Kubernetes cluster stand-in**. This document
explains every container, why it exists, why it was built the way it was,
and every command used to run it.

---

## Table of contents

1. [The mental model](#the-mental-model)
2. [The containers (base stack)](#the-containers-base-stack)
3. [The overlay files](#the-overlay-files)
4. [Why this architecture (and not something else)](#why-this-architecture)
5. [The commands, explained](#the-commands-explained)
6. [Day-2 commands (logs, exec, stats, teardown)](#day-2-commands)
7. [Quick reference](#quick-reference)

---

## The mental model

```
                    ┌──────────────────────────────────────────────┐
   locust ────────► │                 GATEWAY :8080                │
   (load)           │  polls Prometheus (2s) · hysteresis 80/60 ·  │
                    │  PI controller · HMAC signer                 │
                    └──────────┬───────────────────────┬───────────┘
                     CPU < 80  │                CPU ≥ 80 │ (burst)
                               ▼                         ▼
                   nginx VIP :8000            dummy-serverless :8001
                   (round-robin)             (local Azure Function
                               │              stand-in, HMAC-verified)
                    ┌──────────┴──────────┐
                    ▼                     ▼
              dummy-backend-1       dummy-backend-2
              (cpus: 1.0 cap)       (cpus: 1.0 cap)

   cpu-sim :8002 ──► publishes the cAdvisor-shaped CPU metric
   cadvisor  :8082 ──► real per-container metrics
   prometheus :9090 ──► scrapes everything every 2s
   grafana :3000 ──► 12-panel dashboard
```

---

## The containers (base stack)

All ten services live in `docker-compose.yml`. Docker Compose creates a
shared private network (default: `burstops_default`) so containers reach each
other by service name — that is why configs say `http://gateway:8080`, never
`http://localhost:8080`.

### 1. `dummy-backend-1` and `dummy-backend-2` — the "AKS pods"

| Setting | Value | Why |
|---|---|---|
| build | `./dummy-backend` (python:3.12-slim, FastAPI/uvicorn) | The stand-in for 2 Kubernetes pods running the real workload (sieve of Eratosthenes → 168 primes / sum 76127 — a canary: any component returning different numbers is broken). |
| `cpus: "1.0"` | hard CPU cap | **The single most important detail.** The gateway's PromQL is `rate(container_cpu_usage_seconds_total[30s]) * 100` — it measures **core-seconds × 100** (i.e. cores), not % of quota. A container capped at 1.0 core can numerically reach 100, so the 80 threshold is reachable. A 0.3 cap could never cross 80 no matter how hard it burns. |
| `mem_limit: 128m` | memory cap | Keeps the demo light; matches the "small pod" fiction. |
| 1 uvicorn worker | single process | One worker saturating one core is what lets `/burn-cpu` push the observed metric past 80. More workers would spread the burn across cores and dilute the signal. |
| no host ports | — | Nothing reaches the pods directly except through the nginx VIP — exactly like real pods behind a Service. |

### 2. `dummy-backend` — the "K8s Service" (nginx VIP)

- Image: `nginx:1.27-alpine`, port `8000:8000`.
- Mounts `dummy-backend/nginx.conf` read-only. nginx round-robins
  `dummy-backend-1:8000` and `dummy-backend-2:8000` — simulating a Kubernetes
  Service load-balancing across pod replicas.
- `depends_on` the two replicas so the VIP never starts before its upstreams.
- This is the gateway's `K8S_UPSTREAM` target.

### 3. `dummy-serverless` — the local Azure Function stand-in

- Built from `dummy-serverless/` (python:3.12-slim), port `8001`.
- Verifies the **exact HMAC contract** the real Azure Function enforces:
  key → timestamp shape → clock skew ≤ 300 s → signature, in that fixed
  order (a wrong-key caller learns nothing about signature validity).
- Injects 50–150 ms artificial latency so bursting "feels cold-ish" locally.
- Shares `GATEWAY_HMAC_SECRET` and `FUNCTION_KEY` with the gateway via env
  vars — so a local burst demo exercises the identical signed-wire path
  without touching Azure.
- `hmac_util.py` here and in `azure-function/` are byte-identical,
  copy-drift-tested — cheaper than packaging tricks for Azure's single-dir
  deploy model.

### 4. `cpu-sim` — the synthetic cAdvisor

- Built from `cpu-sim/`, port `8002`, starts at `INITIAL_CPU_PCT=20`.
- **Why it exists:** Docker Desktop's cAdvisor runs in restricted mode and
  never publishes usable per-container CPU series — so on macOS there is
  nothing real for the gateway's PromQL to find. cpu-sim publishes
  `container_cpu_usage_seconds_total{namespace="burstops"}` in exactly the
  shape the query expects, with control endpoints:
  - `POST /set?pct=95` — force a burst
  - `POST /ramp-up` / `/ramp-down` — gradual changes
- This is how the burst demo is triggered deterministically in 3 commands.
- Honest limitation (documented): cpu-sim is open-loop — deflecting traffic
  does not cool it down. The closed-loop PI proof lives in the test suite.

### 5. `gateway` — the system itself

- Built from `gateway/` (python:3.12-slim), port `8080`.
- The FastAPI app with the background Prometheus poller, the 80/60
  hysteresis state machine, the PI deflection controller, the HMAC signer,
  `/metrics` exposition, and tracing/backplane hooks.
- `depends_on`: backend VIP, serverless, prometheus, cpu-sim — it is the
  convergence point of the whole stack.
- All knobs come in as env vars with local-dev defaults (`K8S_UPSTREAM`,
  `FUNCTION_UPSTREAM`, `PROMETHEUS_URL`, secrets), so pointing it at the
  **real Azure Function** later is a `.env.azure` overlay — zero file edits.

### 6. `cadvisor` — real container metrics

- Image `gcr.io/cadvisor/cadvisor:v0.49.1`, port `8082:8080`, `privileged: true`.
- Mounts `/`, `/sys`, `/var/run/docker.sock`, `/var/lib/docker` read-only —
  cAdvisor needs to see the host's cgroup tree to report per-container CPU
  and memory.
- On Docker Desktop (macOS) its per-container series are unusable, hence
  cpu-sim; on a real Linux host it works, and Prometheus's relabel rules
  stamp `namespace="burstops"` onto its backend series so the same stack
  works unmodified there.

### 7. `prometheus` — the metric store

- Image `prom/prometheus:v2.53.1`, port `9090`.
- `scrape_interval: 2s` — the whole control loop's latency budget.
- `prometheus/prometheus.yml` has four jobs: cadvisor (CPU/memory series for
  the two backends **only** — relabel rules drop everything else, because
  averaging in Grafana/Locust/Prometheus itself would dilute the signal so
  far below 80 that a burst could never be seen), gateway (`gateway_*`
  metrics), cpu-sim, and itself.
- `--storage.tsdb.retention.time=24h` — a demo does not need a week of
  samples.
- `--web.enable-lifecycle` — allows config reloads without a restart.

### 8. `grafana` — the dashboard

- Image `grafana/grafana:11.1.4`, port `3000` (admin / burstops).
- Mounts `grafana/provisioning` — the datasource (`uid: burstops-prometheus`,
  pointing at `http://prometheus:9090`) and the 12-panel dashboard are
  **auto-provisioned on boot**: no clicking, no "datasource not found".
- `depends_on: prometheus` so the datasource's target exists at startup.

### 9. `locust` — the load generator

- Image `locustio/locust:2.29.1`, UI at port `8089`.
- Mounts `locust/locustfile.py` and runs against `--host http://gateway:8080`.
- Traffic profile: **95% GET /calculate** (organic traffic through the
  gateway) and **5% POST /burn-cpu** fired *directly at the nginx VIP*
  (the gateway only proxies /calculate), so cAdvisor sees genuine CPU load
  on the backend replicas — not simulated numbers.

### 10. `redis` + `jaeger` — overlay-only (see below)

---

## The overlay files

Compose **overlays** are extra YAML files merged on top of the base file.
BurstOps uses them to keep the offline default minimal: a fresh clone
`docker compose up` gets exactly the 10-service stack above, nothing more.

### `docker-compose.scale.yml` — Upgrade B (multi-replica gateway)

Adds **redis** (leader-election backplane) and re-maps the gateway's port:

- `redis:7-alpine` with `--save "" --appendonly no --maxmemory 32mb
  --maxmemory-policy allkeys-lru` — **no persistence, no auth, on purpose**:
  it holds a routing hint any gateway replica can rebuild in one 2 s poll
  cycle; durability would buy nothing, and it is only reachable inside the
  compose network. (Azure Cache for Redis was rejected: the tier is in
  retirement and the successor costs more than the project's whole budget.)
- `ports: !override - "8080"` — the base file pins gateway to a fixed host
  port, which **conflicts with `--scale gateway=3`** (three containers
  cannot all bind host port 8080). The `!override` tag replaces the mapping
  with container-port-only, so Docker assigns each replica an ephemeral
  host port.

### `docker-compose.tracing.yml` — Upgrade D (OpenTelemetry)

Adds **jaeger** (`jaegertracing/all-in-one:1.60`): UI on `16686`, OTLP gRPC
on `4317`, with `COLLECTOR_OTLP_ENABLED=true`. The gateway gets
`OTEL_TRACES_EXPORTER=otlp` + the Jaeger endpoint, so spans flow without a
line of code changing in `gateway.py`.

The file's own header says it: *do not merge into docker-compose.yml —
the offline default has tracing off.*

---

## Why this architecture

Every choice traces back to `docs/architecture-decision.md` — **Option B:
no AKS cluster.** Four hard blockers made a real cluster impossible on an
Azure for Students subscription:

1. **Region lock** — a subscription policy restricts all resources to five
   regions; none offers an AKS-eligible free VM.
2. **No free-grant VM meets AKS's minimum node spec** (≥2 cores AND ≥4 GB —
   every free SKU fails at least one).
3. **The cheapest eligible node (~$30/mo) would exhaust the $100 credit in
   ~3 months** of 24/7 running.
4. The stack is a *student demo* — the point is the gateway's control loop,
   not the substrate.

So the mapping is:

| Kubernetes concept | Docker stand-in |
|---|---|
| 2 AKS pods | `dummy-backend-1/2` (with `cpus: "1.0"` pod resource limits) |
| K8s Service (load balancing) | `nginx` VIP round-robin |
| cAdvisor / kubelet metrics | `cpu-sim` (+ real cAdvisor for Linux hosts) |
| Prometheus + Grafana stack | actual Prometheus + Grafana (identical to prod) |
| Serverless overflow target | `dummy-serverless` locally, real Azure Function via `.env.azure` |
| Multiple gateway replicas | `--scale gateway=3` + redis backplane overlay |

What this preserves: the hysteresis logic, the PromQL, the HMAC wire
contract, the metrics, the dashboards — all byte-identical to what would run
in AKS. What it gives up: real kube-proxy, real HPA, real pod scheduling.
The `k8s/` manifests remain in the repo as the reversal path.

Other deliberate "why"s worth remembering:

- **`python:3.12-slim` everywhere** — small images, fast builds, free.
- **`restart: unless-stopped`** on everything — a crashed demo container
  heals itself; you still keep `docker compose down` control.
- **Read-only (`:ro`) config mounts** — nginx/prometheus/locust/grafana
  configs cannot be mutated by the containers.
- **Secrets via env vars with `${VAR:-default}`** — sane local defaults,
  overridable by `.env` / `.env.azure` without touching any file.

---

## The commands, explained

### Start the base stack

```bash
docker compose up -d --build
```

| Piece | Meaning |
|---|---|
| `docker compose` | reads `docker-compose.yml` in the current directory |
| `up` | creates networks + containers and starts them |
| `-d` | detached — returns your terminal, containers keep running |
| `--build` | forces a rebuild of the four `build:` services (gateway, dummy-backend ×2, dummy-serverless, cpu-sim) before starting. Without it, a changed `gateway.py` would run stale. |

### Verify it came up

```bash
docker compose ps                 # per-service status (Name, State, Ports)
docker compose ps -a              # include stopped/failed containers
curl localhost:8080/health        # {"mode":"baseline",...} — gateway is live
```

### The burst demo (three commands)

```bash
curl -X POST 'localhost:8002/set?pct=95'    # tell cpu-sim the "cluster" is at 95%
sleep 35 && curl localhost:8080/health      # ~30s rate() window + glide → "mode":"burst"
curl localhost:8080/calculate               # "source":"serverless" — HMAC-signed deflection
curl -X POST 'localhost:8002/set?pct=20'    # drop below 60 → recovers to baseline
```

`-X POST` forces the HTTP method; the `?pct=95` query parameter is cpu-sim's
control input. The 35 s wait is the measurement's own lag (the 30 s `rate()`
window), not the gateway being slow.

### Run with an overlay (scale or tracing)

```bash
# 3 gateway replicas + redis backplane:
docker compose -f docker-compose.yml -f docker-compose.scale.yml up -d --build --scale gateway=3

# find the ephemeral host port of replica N:
docker compose -f docker-compose.yml -f docker-compose.scale.yml port --index=2 gateway 8080

# Jaeger tracing:
docker compose -f docker-compose.yml -f docker-compose.tracing.yml up -d --build
```

| Piece | Meaning |
|---|---|
| `-f <file>` | use this compose file; repeatable — later files are **merged over** earlier ones (that is the entire overlay mechanism) |
| `--scale gateway=3` | run 3 instances of the gateway service (works only because the overlay removed the fixed host-port mapping) |
| `port --index=N gateway 8080` | print the host port Compose assigned to replica N's container port 8080 |

### Point the gateway at the REAL Azure Function

```bash
docker compose --env-file .env --env-file .env.azure up -d --force-recreate gateway
```

| Piece | Meaning |
|---|---|
| `--env-file <f>` | load variable substitutions from a file; later files override earlier ones. `.env` (local) stays untouched, `.env.azure` only overrides `FUNCTION_UPSTREAM`, key and secret. |
| `up -d ... gateway` | recreate **only** the gateway with the new environment |
| `--force-recreate` | recreate the container even though its config "looks" unchanged |

### Rebuild after a code change

```bash
docker compose build gateway            # rebuild one service's image
docker compose up -d --build gateway    # rebuild + recreate that service only
docker compose up -d --build            # rebuild + recreate everything
```

Compose caches layers; `COPY` layers rebuild only when the copied files
changed, so a `gateway.py` edit rebuilds in seconds.

### Tear down

```bash
docker compose down                    # stop + remove containers and the network
docker compose down -v                 # ALSO delete named volumes
docker compose -f docker-compose.yml -f docker-compose.scale.yml down   # if you ran with overlays
```

Note: run `down` with the **same `-f` flags** you started with, otherwise
Compose will not find those services. Volumes here are only config mounts
(bind mounts), so plain `down` never deletes your configs.

---

## Day-2 commands

```bash
docker compose logs -f gateway          # follow one service's logs (Ctrl-C to stop)
docker compose logs gateway --tail=50   # last 50 lines only
docker compose logs -f --tail=0 gateway  # only NEW lines from now on

docker compose exec gateway sh          # shell INSIDE a running container
docker compose exec gateway env          # inspect its final environment variables

docker stats --no-stream                # one-shot CPU/memory snapshot of all containers
docker stats burstops-backend-1         # live view of one container

docker compose top gateway              # the processes running inside the service

docker compose restart prometheus       # bounce one service (keeps container)
docker compose up -d --force-recreate prometheus   # full recreate (new env/config)

docker compose pull                     # refresh the prebuilt images (nginx, prom, grafana…)
```

Debugging mental map: `ps` for "is it up" → `logs` for "what did it say" →
`exec` for "what does it see" → `stats`/Grafana for "what is it doing".

### Useful endpoints once the stack is up

| URL | What |
|---|---|
| `http://localhost:8080/health` | gateway mode (baseline/burst) + observed CPU |
| `http://localhost:8080/calculate` | the routed request itself |
| `http://localhost:8080/metrics` | all `gateway_*` Prometheus metrics |
| `http://localhost:8002/set?pct=N` | cpu-sim burst control |
| `http://localhost:9090/targets` | Prometheus scrape health |
| `http://localhost:3000` | Grafana (admin / burstops) |
| `http://localhost:8089` | Locust load UI |
| `http://localhost:16686` | Jaeger UI (tracing overlay only) |
| `http://localhost:8082` | cAdvisor UI |

---

## Quick reference

```bash
# base stack
docker compose up -d --build
docker compose ps
curl localhost:8080/health

# burst demo
curl -X POST 'localhost:8002/set?pct=95'
sleep 35 && curl localhost:8080/health
curl localhost:8080/calculate
curl -X POST 'localhost:8002/set?pct=20'

# 3 replicas + redis
docker compose -f docker-compose.yml -f docker-compose.scale.yml up -d --build --scale gateway=3
docker compose -f docker-compose.yml -f docker-compose.scale.yml port --index=N gateway 8080

# tracing
docker compose -f docker-compose.yml -f docker-compose.tracing.yml up -d --build

# real Azure Function
docker compose --env-file .env --env-file .env.azure up -d --force-recreate gateway

# teardown
docker compose down
```
