# Everything About BurstOps — The Complete Technical Architectural & Operational Guide

This document is an exhaustive, start-to-finish technical guide for the **BurstOps** project. It details the problem it solves, how the work was structured across all 12 phases/milestones, the end-to-end system architecture, how the project operates locally versus on Microsoft Azure, the full request lifecycle, all four system upgrades, the purpose of every Terraform file, and how to verify and operate the entire system.

---

## Table of Contents

1. [Executive Summary & Core Problem Solved](#1-executive-summary--core-problem-solved)
2. [The 12 Project Phases & Work Division](#2-the-12-project-phases--work-division)
3. [End-to-End System Architecture](#3-end-to-end-system-architecture)
4. [Local vs. Azure Cloud Implementation](#4-local-vs-azure-cloud-implementation)
5. [The System Contract & Workflows](#5-the-system-contract--workflows)
6. [Deep-Dive into the Four Upgrades (A–D)](#6-deep-dive-into-the-four-upgrades-ad)
7. [Terraform Files & Infrastructure as Code (IaC)](#7-terraform-files--infrastructure-as-code-iac)
8. [The Decision Log: What Was Excluded & Why](#8-the-decision-log-what-was-excluded--why)
9. [Verification, Testing & Operational Runbook](#9-verification-testing--operational-runbook)
10. [FinOps, Cost Accounting & Teardown](#10-finops-cost-accounting--teardown)

---

## 1. Executive Summary & Core Problem Solved

### What is BurstOps?
**BurstOps** is a resilient **Layer-7 traffic gateway** designed to act as an operational **shock absorber** for Kubernetes clusters facing abrupt traffic surges.

### The Problem: Kubernetes HPA Provisioning Lag
Kubernetes Horizontal Pod Autoscaler (HPA) scales pods based on metrics like CPU utilization. However, in production:
1. **Metrics Delay**: Metrics scrapers (Metrics Server / Prometheus / cAdvisor) take 15–30 seconds to collect and smooth container CPU usage metrics.
2. **HPA Evaluation Delay**: HPA evaluates metrics periodically (default every 15 seconds).
3. **Scheduling & Pod Initialization**: Once triggered, scheduling, pulling images, running container runtimes, starting application frameworks, and passing readiness probes takes another **30 to 90+ seconds**.
4. **The "Meltdown" Window**: During these 30–90+ seconds of sudden traffic spikes, existing pods are overwhelmed by traffic, leading to 100% CPU saturation, queue pileups, high latencies, cascading timeouts, and 504 Gateway Timeouts for users.

### The BurstOps Solution: A Shock Absorber, Not an HPA Replacement
BurstOps does not replace HPA; it **buys HPA time**:
- The gateway continuously watches cluster CPU utilization in real time (2-second polling).
- The instant CPU crosses the safety threshold (**80% CPU**), BurstOps enters `BURST` mode and instantaneously deflects excess overflow traffic to a serverless backend (**Azure Functions** or a local serverless stand-in).
- Serverless responds immediately (in milliseconds or ~1s cold start) with near-infinite auto-concurrency.
- When cluster CPU drops safely below **60%**, BurstOps smoothly redirects all traffic back to the Kubernetes baseline.
- Pods never crash or drop connections during the HPA provisioning window.

---

## 2. The 12 Project Phases & Work Division

The project was executed incrementally through a structured prompt pack and handoff documentation. Each phase created clean, decoupled components governed by immutable architectural contracts.

| Phase / File | Focus Area | Deliverables & Significance |
|---|---|---|
| **01** (`01-phase0a-dummy-backend-build-and-grafana.md`) | **Base Cluster & Observability** | • Created `dummy-backend/Dockerfile` and `requirements.txt`.<br>• Configured 2 replica containers behind an Nginx reverse proxy VIP (:8000).<br>• Provisioned Grafana datasource pointing to Prometheus (`uid: burstops-prometheus`).<br>• Standardized the work canary: Sieve of Eratosthenes (2..1000) yielding 168 primes with sum 76127. |
| **02** (`02-phase0b-dummy-serverless.md`) | **Local Serverless Stand-In & Security** | • Built `dummy-serverless/` (port 8001).<br>• Implemented HMAC-SHA256 verification utility (`hmac_util.py`).<br>• Added artificial latency injection (50–150ms) to simulate serverless network hops/cold starts.<br>• Built 18-case test suite (`test_hmac_contract.py`) covering 4 golden vectors, timestamp skew (300s limit), and tampering. |
| **03** (`03-phase0c-cpu-sim-and-acceptance.md`) | **Synthetic Metrics & Full Acceptance** | • Built `cpu-sim/` (port 8002): Docker Desktop's cAdvisor cannot publish per-container CPU metrics on macOS/Windows, so `cpu-sim` publishes standard PromQL-compatible `container_cpu_usage_seconds_total{namespace="burstops"}` metrics with `/ramp-up`, `/ramp-down`, and `/set?pct=X` endpoints.<br>• Conducted full local stack acceptance across all 10 Docker services. |
| **04** (`04-phase4-azure-function.md`) | **Real Cloud Target** | • Built `azure-function/` using the **Azure Functions Python V2 programming model**.<br>• Verbatim port of `hmac_util.py` (ensuring 0 drift between local and cloud verifiers).<br>• Single dependency (`azure-functions==1.25.0`) to keep cold starts sub-second. |
| **05** (`05-phase5-terraform.md`) | **Infrastructure as Code (IaC)** | • Built the Terraform stack (`terraform/`) for Azure.<br>• Resource Group, Storage Account, Log Analytics workspace, Application Insights (daily cap 0.15 GB to guarantee free tier), Flex Consumption Function, and Monthly Budget Alert ($50 limit).<br>• Automated 48-character random HMAC secret injection without human handling. |
| **06** (`06-phase6-aks-ingress.md`) | **Production Decision & Hybrid Bridge** | • Outlined the AKS manifests (`k8s/`).<br>• Evaluated student subscription region and SKU quotas.<br>• Enacted **Option B Architecture Decision**: Local Docker Compose acts as the cluster stand-in, while the real Azure Function acts as the live cloud burst target via `.env.azure` overlay. |
| **07** (`07-upgrade-a-proportional-deflection.md`) | **Upgrade A: PI Controller** | • Replaced binary (0% or 100%) deflection with continuous **Proportional-Integral (PI) control**.<br>• Setpoint at 75% CPU (inside the 60–80 dead band).<br>• Conditional anti-windup to prevent integral runaway.<br>• Slew-rate limiting (0.10/s) for stability.<br>• Bernoulli randomized routing per request. |
| **08** (`08-upgrade-b-redis-backplane.md`) | **Upgrade B: Distributed State & Scale** | • Built `redis_backplane.py` to allow N gateway replicas.<br>• Separated control plane (1 leader polling Prometheus) from data plane (stateless routing).<br>• Lua-based atomic Compare-And-Set (CAS) leader election and lease renewal.<br>• In-memory local cache on followers for zero Redis I/O on the request path.<br>• 4-second failover on leader crash. |
| **09** (`09-upgrade-c-finops-telemetry.md`) | **Upgrade C: FinOps Telemetry** | • Built `costing.py` for cloud unit economics.<br>• Modeled amortized Kubernetes cost vs. serverless invocation costs (100ms billing floor, 128MB ceiling).<br>• Calculated breakeven overflow rate (28.55 RPS).<br>• Tracked HPA provisioning lag cost window (`gateway_hpa_lag_cost_usd_total`). |
| **10** (`10-upgrade-d-opentelemetry.md`) | **Upgrade D: OpenTelemetry Tracing** | • Built `tracing.py` to inject W3C `traceparent` headers.<br>• Added routing-aware adaptive sampling (100% of burst requests, 5% of baseline).<br>• Zero modifications to `gateway.py` (clean entrypoint attachment).<br>• Cryptographic credential sanitization (no HMAC secrets or signatures in spans). |
| **11** (`README.md` & `VERIFY.md`) | **Master Documentation & Verification** | • Comprehensive project documentation, mathematical formulations, 89 green tests catalog, and copy-pasteable verification guide. |
| **12** (`docker.md`) | **Local Stack Deep-Dive** | • Detailed breakdown of all 10 Docker containers, network topology, overlay architectures, and Day-2 operational commands. |

---

## 3. End-to-End System Architecture

### Architectural Diagram

```mermaid
flowchart TD
    subgraph Clients["Load Generator & Clients"]
        Locust["Locust Load Generator\n:8089"]
        Curl["HTTP Clients / curl"]
    end

    subgraph GatewaySubsystem["BurstOps Gateway Subsystem :8080"]
        Entrypoint["gateway_entrypoint.py\n(Env-Var Shim & Hooks)"]
        Router["L7 Router & Bernoulli Dispatcher\n(FastAPI in gateway.py)"]
        StateEngine["Routing State Machine\n(Hysteresis 80 / 60)"]
        PIController["PI Proportional Controller\n(Setpoint: 75% CPU)"]
        Poller["Prometheus Poller Thread\n(Every 2.0s)"]
        Signer["HMAC-SHA256 Signer\n(Timestamp + Signature Headers)"]
        Backplane["Redis Backplane Client\n(Lua CAS Leader Lease)"]
        Tracer["OpenTelemetry Tracer\n(W3C Traceparent Injector)"]
    end

    subgraph LocalCluster["Local Cluster Simulation (Docker Compose)"]
        Prom["Prometheus :9090\n(Scrapes at 2s interval)"]
        Cadvisor["cAdvisor :8082\n(Container metrics)"]
        CPUSim["cpu-sim :8082\n(Synthetic cAdvisor + Ramp Controls)"]
        NginxVIP["Nginx VIP :8000\n(Round-Robin Service Stand-in)"]
        Backend1["dummy-backend-1\n(FastAPI Prime Sieve)"]
        Backend2["dummy-backend-2\n(FastAPI Prime Sieve)"]
        Redis["Redis :6379\n(Distributed Lease & State)"]
        Grafana["Grafana :3000\n(12-Panel Monitoring Dashboard)"]
        Jaeger["Jaeger :16686\n(OTel Distributed Tracing UI)"]
    end

    subgraph ServerlessTargets["Serverless Upstreams (Burst Targets)"]
        DummyServerless["dummy-serverless :8001\n(Local Stand-in + Latency Sim)"]
        AzureFunc["Azure Function App (Flex Consumption)\nfunc-burstops-cvkzqc.azurewebsites.net\n(Real Cloud Python 3.13)"]
    end

    %% Client flows
    Locust -->|HTTP /calculate| Entrypoint
    Curl -->|HTTP /calculate| Entrypoint
    Entrypoint --> Router

    %% Internal gateway control loop
    Poller -->|Queries PromQL every 2s| Prom
    Prom -->|Scrapes container CPU| CPUSim
    Prom -->|Scrapes system containers| Cadvisor
    Poller --> StateEngine
    StateEngine --> PIController
    StateEngine -.-> Backplane
    Backplane -.->|Elects leader / syncs state| Redis
    PIController -->|Sets deflection ratio r| Router

    %% Routing decisions
    Router -->|Baseline Route: 1 - r| NginxVIP
    NginxVIP --> Backend1
    NginxVIP --> Backend2

    Router -->|Burst Route: Deflection r| Signer
    Signer --> Tracer
    Tracer -->|Local Offline Mode| DummyServerless
    Tracer -->|Hybrid Mode (.env.azure)| AzureFunc

    %% Metrics and Traces
    Prom -->|Scrapes /metrics| Router
    Grafana -->|Reads metrics| Prom
    Tracer -.->|OTLP gRPC| Jaeger
```

### Control Plane vs. Data Plane Separation
BurstOps achieves extreme latency efficiency by decoupling the control loop from the request execution path:
- **Control Plane (Async Background Loop)**:
  - Every 2 seconds, the poller thread queries Prometheus for cluster CPU.
  - The hysteresis state machine evaluates state transitions (Baseline vs. Burst).
  - The PI controller recalculates the error `e = CPU - 75.0` and adjusts the deflection ratio `r`.
  - In a multi-replica setup, only the elected leader executes this loop and publishes state to Redis.
- **Data Plane (Synchronous Request Path)**:
  - Incoming requests to `/calculate` perform **zero Prometheus I/O** and **zero Redis I/O**.
  - The router checks the current in-memory deflection ratio `r`.
  - A fast in-memory Bernoulli trial (`random.random() < r`) determines whether the request goes to the Kubernetes backend or the Serverless upstream.
  - If serverless, the HMAC signer computes the SHA256 signature in memory (~50 microseconds) and forwards the request.

---

## 4. Local vs. Azure Cloud Implementation

One of the project's defining engineering accomplishments is its dual-mode execution model: the local stack acts as an authentic stand-in for Kubernetes without incurring cloud fees, while seamlessly maintaining the ability to route burst traffic to real Azure infrastructure.

### The Local Architecture (10 Docker Compose Services)

Docker Compose hosts 10 coordinated services to mirror an entire production Kubernetes ecosystem:

1. **`gateway` (Port 8080)**: The core FastAPI reverse proxy, hysteresis state machine, and PI controller.
2. **`dummy-backend-1` & `dummy-backend-2`**: Two separate Python FastAPI containers executing the prime sieve work canary. Each container is pinned to `cpus: 1.0` so that core-seconds math behaves realistically.
3. **`dummy-backend` (Port 8000)**: An Alpine Nginx reverse proxy load-balancing between `dummy-backend-1` and `dummy-backend-2`. Simulates a Kubernetes `ClusterIP` Service.
4. **`dummy-serverless` (Port 8001)**: Local Azure Function emulator. Enforces the identical cryptographic HMAC-SHA256 verification and introduces randomized 50–150ms delay to simulate serverless cold/warm invocations.
5. **`cpu-sim` (Port 8002)**: Generates synthetic cAdvisor time-series metrics (`container_cpu_usage_seconds_total{namespace="burstops"}`). Docker Desktop on macOS/Windows cannot expose cAdvisor per-container core usage, so `cpu-sim` bridges this gap with full manual controls (`/set?pct=95`, `/ramp-up`, `/ramp-down`).
6. **`cadvisor` (Port 8082)**: Real Google cAdvisor container scraper.
7. **`prometheus` (Port 9090)**: Collects metrics from all components every 2 seconds. Relabel configurations isolate the `burstops` namespace.
8. **`grafana` (Port 3000)**: Visualization platform auto-provisioned with 12 real-time dashboards monitoring CPU, routing modes, latencies, deflection ratios, and FinOps costs.
9. **`locust` (Port 8089)**: Load testing engine sending 95% GET `/calculate` requests through the gateway and 5% POST `/burn-cpu` directly to the backend.
10. **`redis` (Port 6379, via `docker-compose.scale.yml`)**: In-memory distributed backplane for multi-replica leader election and state synchronization.

### The Azure Cloud Architecture (Free-Tier Stack)

The cloud side is deployed on Microsoft Azure under strict cost constraints:

| Azure Resource | Resource Name | SKU / Configuration | Cost / Month | Function in Architecture |
|---|---|---|---|---|
| **Resource Group** | `rg-burstops-prod` | East Asia / Central India | $0.00 | Logical boundary for all cloud assets. |
| **Function App** | `func-burstops-cvkzqc` | **Flex Consumption (FC1)** Python 3.13 | $0.00 (Free grant: 1M calls + 400k GB-s) | Live burst upstream target running the HMAC-protected prime sieve. |
| **Storage Account** | `stburstopscvkzqc` | Standard LRS | ~$0.05 (From credits) | Mandatory runtime requirement for Azure Functions blob/file storage. |
| **Log Analytics** | `log-burstops-cvkzqc` | PerGB2018 | $0.00 (5 GB/mo free grant) | Centralized telemetry and query workspace. |
| **App Insights** | `appi-burstops-cvkzqc` | Daily Cap: **0.15 GB/day** | $0.00 | Performance monitoring, invocation tracking, and distributed tracing. |
| **Cost Budget** | `budget-burstops` | $50 Limit, alerts at 50%, 80%, 100% | $0.00 | Spend guardrail preventing unexpected credit drain. |

### The Hybrid Connection: How Local Talks to Azure

To connect the local gateway to the live Azure Function without modifying source code or default configuration:
1. Azure generates a Function Key for `calculate`.
2. The operator extracts this key using the Azure CLI:
   ```bash
   KEY=$(az functionapp keys list -g rg-burstops-prod -n func-burstops-cvkzqc --query 'functionKeys.default' -o tsv)
   ```
3. A local `.env.azure` file (gitignored) is populated:
   ```env
   FUNCTION_UPSTREAM=https://func-burstops-cvkzqc.azurewebsites.net/api/calculate
   FUNCTION_KEY=<secret-key>
   GATEWAY_HMAC_SECRET=<48-char-terraform-secret>
   ```
4. The gateway is restarted using the Docker Compose overlay:
   ```bash
   docker compose --env-file .env --env-file .env.azure up -d --force-recreate gateway
   ```
The local gateway immediately routes burst traffic across the internet to the real Azure Function, receiving authenticated responses with `{"source": "serverless", "impl": "azure-function"}`.

---

## 5. The System Contract & Workflows

### The Invariant Contract
To maintain complete compatibility across local and cloud environments, five architectural rules are strictly maintained:

1. **HMAC Signing Formula**:
   $$\text{signature} = \text{HMAC-SHA256}\left(\text{secret}, \text{timestamp} + \text{":"} + \text{body}\right).\text{hexdigest}()$$
   - Headers: `x-functions-key`, `x-gateway-timestamp`, `x-gateway-signature`.
   - Max allowable clock skew: **300 seconds (5 minutes)**.
   - Timing-attack-resistant verification: `hmac.compare_digest()`.
2. **Work Canary Calculation**:
   - Every worker (backend or serverless) executes a Sieve of Eratosthenes from 2 to 1000.
   - Result: Exactly **168 primes** with a total sum of **76,127**. Any node producing a different result fails immediately.
3. **Thresholds & Timing**:
   - **Burst Threshold**: CPU $\ge 80.0\%$.
   - **Recovery Threshold**: CPU $< 60.0\%$.
   - **Dead Band**: $60.0\% \le \text{CPU} < 80.0\%$ (state remains unchanged to prevent flapping).
   - **Stale Poll Grace**: 15 seconds. If Prometheus fails to respond for >15s, the gateway **fails open to BURST** (deflecting to serverless is safer than crashing the cluster).
4. **Ports**:
   - Gateway: `8080`
   - Nginx Backend VIP: `8000`
   - Serverless Stand-In: `8001`
   - CPU Simulator: `8002`
   - cAdvisor: `8082`
   - Prometheus: `9090`
   - Grafana: `3000`
   - Locust: `8089`
   - Jaeger: `16686`
5. **The Entrypoint Shim Pattern**:
   - `gateway/gateway.py` is an immutable reference specification.
   - `gateway/gateway_entrypoint.py` monkey-patches configuration at container boot from environment variables, attaching tracing and backplane hooks cleanly.

---

## 6. Deep-Dive into the Four Upgrades (A–D)

### Upgrade A: Proportional Deflection (PI Controller)
Binary bang-bang control (100% k8s below 80% CPU; 100% serverless above 80%) creates severe oscillation. In 100% deflection, cluster CPU plunges to 0%, the gateway flips back to k8s, and the cluster is slammed again.

Upgrade A solves this by implementing continuous **Proportional-Integral (PI)** control:
- **Target Setpoint**: **75.0% CPU** (positioned inside the 60–80% hysteresis dead band so the state machine and controller never fight).
- **Proportional Term**: $P = K_p \cdot e$, where $K_p = 0.04$ and $e = \text{CPU} - 75.0$.
- **Integral Term**: $I_{t} = I_{t-1} + K_i \cdot e \cdot \Delta t$, where $K_i = 0.004$.
- **Conditional Anti-Windup**: The integrator freezes accumulation whenever the output saturates ($r \ge 1.0$ or $r \le 0.0$) in the direction of the error. This prevents the controller from staying deflected for minutes after load drops.
- **Slew-Rate Limiting**: Maximum change of **0.10/second** (~10 seconds to transition 0% to 100%). This keeps the controller slower than the 30-second smoothing window of the plant, guaranteeing stability.
- **Derivative Term Omitted**: The Prometheus signal is already smoothed over a 30s rate window. A derivative term would amplify scrape noise without improving response.
- **Bernoulli Routing**: Each request performs an independent random draw against the ratio $r$. This is stateless and scales across multiple gateway replicas without synchronized counters.

### Upgrade B: Distributed Redis Backplane
When running multiple gateway replicas behind a load balancer, each instance would poll Prometheus independently and make conflicting routing decisions (split-brain).

Upgrade B separates control and data:
- **Leader Election via Lua CAS**:
  - Replicas compete to acquire a distributed Redis lock key (`burstops:leader`) with a 6-second TTL.
  - Lease extension is executed via an atomic Lua Compare-And-Set script that verifies the caller holds the lease before extending it:
    ```lua
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('pexpire', KEYS[1], ARGV[2])
    else
        return 0
    end
    ```
- **State Broadcast**: The elected leader polls Prometheus, calculates the state and deflection ratio, and broadcasts updates over Redis Pub/Sub with an incrementing generation counter.
- **Zero I/O Data Plane**: Follower replicas store the latest state in local RAM. Request handling never touches Redis.
- **Degradation Ladder**:
  1. Fresh Redis state available $\rightarrow$ Use state.
  2. Redis down or stale $\rightarrow$ Degrade to independent Prometheus polling.
  3. Prometheus unreachable for >15s $\rightarrow$ Fail open to BURST.

### Upgrade C: FinOps Telemetry & Unit Economics
Bursting to serverless is an availability choice, not a cost-saving one: the Kubernetes node bill is already sunk.

Upgrade C models the real unit economics:
- **Kubernetes Unit Cost**: Amortized cost of a Standard_B2s VM ($0.0416/hr) at 50 RPS capacity:
  $$\text{Cost}_{\text{k8s}} = \$2.3111 \times 10^{-7} \text{ USD per request}$$
- **Serverless Unit Cost**: Azure Consumption pricing ($0.20/million requests + $0.000016/GB-s) with 100ms minimum billing floor and 128MB memory ceiling:
  $$\text{Cost}_{\text{serverless}} = \$4.0480 \times 10^{-7} \text{ USD per request}$$
- **Deflection Premium**: Deflecting traffic costs **~1.75× more** than handling it in-cluster ($+\$1.7369 \times 10^{-7}/\text{req}$).
- **Breakeven Overflow Rate**:
  $$\text{Breakeven RPS} = \frac{\text{Node Cost per Second}}{\text{Serverless Unit Cost}} = 28.55 \text{ RPS}$$
  - If sustained overflow is **$< 28.55$ RPS**, serverless bursting is cheaper than provisioning another cluster node.
  - If sustained overflow is **$> 28.55$ RPS**, scaling up the cluster with a new VM node is cheaper.
- **HPA Lag Window Metric**: `gateway_hpa_lag_cost_usd_total` tracks the cost accrued specifically during the first 120 seconds of each burst episode—the exact metric justifying the ROI of the gateway.

### Upgrade D: OpenTelemetry Distributed Tracing
Provides end-to-end trace correlation from client to gateway to serverless upstreams:
- **Zero Modifications to Core Spec**: Hooks dynamically attached via `FastAPIInstrumentor` and `HTTPXClientInstrumentor` in `gateway_entrypoint.py`.
- **Adaptive Routing-Aware Sampling**:
  - **100% of requests during BURST** are sampled (preserving rare incident traces).
  - **5% of requests during BASELINE** are sampled (preventing storage bloat).
- **W3C `traceparent` Propagation**: Downstream spans injected into HTTP headers. Since headers are outside the signed payload, HMAC verification remains valid.
- **Credential Redaction Guardrails**: Exported spans are audited; headers like `x-gateway-signature` and `x-functions-key` are strictly scrubbed.
- **Non-Blocking Architecture**: Always uses `BatchSpanProcessor` so tracing network I/O never adds latency to client requests.

---

## 7. Terraform Files & Infrastructure as Code (IaC)

All Azure resources are declaratively defined in the `terraform/` directory.

```
terraform/
├── providers.tf            # AzureRM provider configuration
├── versions.tf             # Terraform & provider version constraints
├── variables.tf            # Configurable inputs, region constraints & limits
├── main.tf                 # Core Azure resources: RG, Storage, Flex Function, App Insights
├── identity.tf             # Cryptographic random secret generation (HMAC)
├── budget.tf               # Consumption budget & alerting rules
├── outputs.tf              # Non-sensitive endpoints & resource identifiers
├── terraform.tfvars.example# Template for operator inputs
└── terraform.tfstate       # Local state file (gitignored, contains HMAC secret)
```

### Detailed Breakdown of Every Terraform File

#### 1. `providers.tf`
Configures the `azurerm` provider with required features block. Ensures all resources inherit standard Azure APIs.

#### 2. `versions.tf`
Locks provider constraints to prevent breaking changes:
- `terraform >= 1.9.0`
- `azurerm >= 3.100.0, < 5.0.0`
- `random >= 3.5.0`

#### 3. `variables.tf`
Declares input variables with defaults tailored to free-tier constraints:
- `subscription_id`: Azure subscription ID.
- `location`: Default `eastasia` (selected among the 5 policy-allowed regions for full service availability).
- `environment`: Set to `prod`.
- `python_version`: Set to `3.13` (newest stable Linux runtime).
- `monthly_budget_usd`: Set to `$50` as a spending ceiling.
- `budget_alert_emails`: List of emails receiving automated threshold notifications.
- `log_daily_cap_gb`: Capped at **0.15 GB/day** ($0.15 \times 30 = 4.5\text{ GB/mo}$), mathematically guaranteeing the 5 GB/month free log grant is never exceeded.

#### 4. `main.tf`
The primary infrastructure definition:
- `azurerm_resource_group.main`: `rg-burstops-prod`.
- `random_string.suffix`: Generates a unique 6-character lowercase suffix for globally unique names.
- `azurerm_storage_account.main`: Standard LRS storage required by the Azure Functions host runtime (~$0.05/mo).
- `azurerm_storage_container.flex_deploy`: Private blob container for Flex Consumption deployment packages.
- `azurerm_log_analytics_workspace.main`: Log analytics backend with 30-day retention.
- `azurerm_application_insights.main`: Application monitoring tied to the Log Analytics workspace.
- `azurerm_service_plan.main`: Linux App Service Plan on the `FC1` (Flex Consumption) SKU.
- `azurerm_function_app_flex_consumption.main`:
  - Enforces HTTPS only and TLS 1.2 minimum.
  - Injects `MAX_CLOCK_SKEW_SECONDS = "300"`.
  - Injects `GATEWAY_HMAC_SECRET` from `identity.tf`.
  - Configures System-Assigned Managed Identity.

#### 5. `identity.tf`
Generates the cryptographic HMAC key:
- `random_password.gateway_hmac_secret`:
  - 48 characters in length.
  - `special = false` to guarantee safe transport across HTTP headers and shell variables without escaping issues.
  - Eliminates human secret generation and avoids expensive Key Vault instances ($0.03/10k operations). The secret is stored directly in encrypted app settings and `terraform.tfstate`.

#### 6. `budget.tf`
Prevents billing runaway:
- `azurerm_consumption_budget_resource_group.main`:
  - Evaluated on a monthly grain.
  - Notifications triggered at **50%**, **80%**, and **100%** of the $50 budget limit.
  - Sends immediate email alerts if unexpected compute or storage charges occur.

#### 7. `outputs.tf`
Exports connection details while preventing secret leakage:
- `function_app_name`: Name of the deployed function.
- `function_hostname`: Target URL (`https://.../api/calculate`).
- `resource_group_name`: `rg-burstops-prod`.
- `storage_account_name`: Name of the storage account.
- `app_insights_connection_string`: Marked with `sensitive = true` to prevent terminal log exposure.
- Note: The HMAC secret and Function key are intentionally omitted from outputs.

---

## 8. The Decision Log: What Was Excluded & Why

The repository includes a strict architectural decision record (`docs/architecture-decision.md`). Every exclusion represents a deliberate trade-off prioritizing cost minimization and correctness:

1. **Why No Real AKS Cluster on Azure?**
   - **Region Lockout**: The Azure for Students subscription is restricted by policy (`sys.regionrestriction`) to 5 regions: `centralindia, austriaeast, uaenorth, eastasia, malaysiawest`.
   - **SKU Quotas**: Free student VM grants cover `B1s` (1 core) and `B2ats_v2`/`B2pts_v2` (1 GB RAM). AKS requires nodes with **$\ge 2$ cores AND $\ge 4$ GB RAM**. Every free SKU fails one of these criteria.
   - **Budget Burn**: The cheapest eligible VM (`Standard_B2s_v2`) costs ~$30/month. Running an AKS cluster 24/7 would exhaust the $100 student credit in ~3 months.
   - **Decision**: The local Docker Compose stack acts as the Kubernetes cluster. It executes the exact same container images, networking, and metrics query.
2. **Why No Azure Container Registry (ACR)?**
   - Without an in-cloud AKS cluster pulling images, ACR is an idle cost ($5/month after promotional period). Deleted to maintain $0 spend.
3. **Why No Azure Key Vault?**
   - Key Vault incurs per-transaction API billing ($0.03/10k operations). Injecting the HMAC secret as an encrypted App Setting is free and encrypted at rest.
4. **Why No Azure Cache for Redis?**
   - Azure Cache for Redis Basic/Standard/Premium is deprecated and retirement-scheduled. Azure Managed Redis starts at ~$15/month. A lightweight Redis container in Docker Compose provides identical Lua CAS semantics at $0 cost.
5. **Why Flex Consumption instead of Classic Consumption (Y1)?**
   - During Phase 4 deployments, Classic Consumption stamps returned persistent 503 Internal Server Errors across multiple Azure regions due to platform runtime provisioning faults. Flex Consumption utilizes modern containerized host runtimes and provisions reliably.

---

## 9. Verification, Testing & Operational Runbook

### Running the 89-Test Automated Suite
The repository includes an exhaustive test suite covering every system invariant:

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r gateway/requirements.txt pytest pytest-asyncio \
  opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc \
  opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-httpx redis

# 3. Execute tests
pytest tests/ -v
```

#### Test Suite Breakdown (89 Tests)
- `test_hysteresis.py` (6 tests): Validates 80% burst flip, 60% recovery, dead band retention, and 15s stale fail-open.
- `test_hmac_contract.py` (18 tests): Pins 4 golden HMAC vectors, validates timestamp skew limits (300s), and guarantees 0 drift between `dummy-serverless` and `azure-function` copies of `hmac_util.py`.
- `test_proportional_deflection.py` (14 tests): Validates PI mathematical accuracy, anti-windup clamping, slew limiting, and closed-loop plant simulation settling at ratio 0.625.
- `test_costing.py` (26 tests): Verifies 100ms billing floors, 128MB RAM stepping, breakeven math (28.55 RPS), and HPA lag window counters.
- `test_redis_backplane.py` (10 tests): Verifies Lua Compare-And-Set leader leases, failover within 4 seconds, generation guards, and graceful degradation.
- `test_tracing.py` (13 tests): Validates W3C traceparent propagation, routing-aware sampling, span attribute scrubbing, and verifies `gateway.py` has zero uncommitted diffs.

---

### Step-by-Step Verification Runbook

#### Step 1: Start the Base Local Stack
```bash
docker compose up -d --build
```
Wait 20 seconds for services to initialize, then verify:
```bash
# Health check (should report baseline)
curl -s http://localhost:8080/health | jq .

# Request execution (should report source: k8s, 168 primes, sum 76127)
curl -s http://localhost:8080/calculate | jq .
```

#### Step 2: Simulate a Traffic Surge & Observe Burst Mode
```bash
# Saturate synthetic cluster CPU to 95%
curl -X POST 'http://localhost:8002/set?pct=95'

# Wait 35 seconds (30s rate window + 5s glide)
sleep 35

# Verify gateway flipped to burst
curl -s http://localhost:8080/health | jq .

# Verify requests are now deflected to serverless (source: serverless)
curl -s http://localhost:8080/calculate | jq .
```

#### Step 3: Observe Recovery Back to Baseline
```bash
# Reduce synthetic CPU to 20%
curl -X POST 'http://localhost:8002/set?pct=20'

# Wait 35 seconds
sleep 35

# Verify gateway returned to baseline
curl -s http://localhost:8080/health | jq .
```

#### Step 4: Route Traffic to the Real Azure Function
```bash
# Log in and fetch live Function Key
az login
KEY=$(az functionapp keys list -g rg-burstops-prod -n func-burstops-cvkzqc --query 'functionKeys.default' -o tsv)

# Create .env.azure
cat <<EOF > .env.azure
FUNCTION_UPSTREAM=https://func-burstops-cvkzqc.azurewebsites.net/api/calculate
FUNCTION_KEY=$KEY
GATEWAY_HMAC_SECRET=$(cd terraform && terraform output -raw gateway_hmac_secret 2>/dev/null || grep GATEWAY_HMAC_SECRET .env | cut -d= -f2)
EOF

# Restart gateway with Azure overlay
docker compose --env-file .env --env-file .env.azure up -d --force-recreate gateway

# Trigger burst and verify live Azure execution
curl -X POST 'http://localhost:8002/set?pct=95'
sleep 35
curl -s http://localhost:8080/calculate | jq .
# Expected output contains: "impl": "azure-function"
```

#### Step 5: Multi-Replica Scale & Failover Verification
```bash
# Launch 3 gateway replicas with Redis backplane
docker compose -f docker-compose.yml -f docker-compose.scale.yml up -d --build --scale gateway=3

# Verify leader election (exactly one leader exists)
for i in 1 2 3; do
  PORT=$(docker compose -f docker-compose.yml -f docker-compose.scale.yml port --index=$i gateway 8080 | cut -d: -f2)
  echo "Instance on port $PORT:"
  curl -s http://localhost:$PORT/metrics | grep -E '^gateway_is_leader'
done
```

---

## 10. FinOps, Cost Accounting & Teardown

### Monthly Steady-State Cloud Bill

| Service | Tier / SKU | Monthly Usage | Cost | Paid By |
|---|---|---|---|---|
| Azure Function | Flex Consumption | < 50,000 requests | $0.00 | Free grant (1M executions/mo free) |
| Storage Account | Standard LRS | < 1 GB blob data | ~$0.05 | Student Credit ($100 balance) |
| Log Analytics | PerGB2018 | < 0.15 GB/day | $0.00 | Free grant (5 GB/mo free) |
| Application Insights | Basic | Sampled traces | $0.00 | Free grant |
| Outbound Bandwidth | Standard Egress | < 1 GB egress | $0.00 | Free grant (100 GB/mo free) |
| **Total Steady State** | | | **~$0.05 / month** | **$0.00 Out of Pocket** |

### Complete Teardown Procedures

#### 1. Stop and Clean Local Environment
```bash
# Stop all containers, remove networks and volumes
docker compose down -v
docker compose -f docker-compose.yml -f docker-compose.scale.yml down -v
docker compose -f docker-compose.yml -f docker-compose.tracing.yml down -v
```

#### 2. Destroy Azure Cloud Infrastructure
```bash
# Destroy all Azure resources managed by Terraform
cd terraform
terraform destroy -auto-approve

# Verify resource group removal
az group exists -n rg-burstops-prod   # returns false
```

---

## Summary of Completed Deliverables

1. **Complete Hybrid Architecture**: Local Kubernetes stand-in cluster paired with an authenticated, serverless Azure Function.
2. **Cryptographic Security**: HMAC-SHA256 request signing and timing-safe verification preventing replay attacks and key leakage.
3. **Advanced Control Theory**: Dual-layer control incorporating dead-band hysteresis (80/60) and a Proportional-Integral (PI) controller with anti-windup.
4. **Resilient Scale**: Multi-replica gateway coordination via Redis Lua Compare-And-Set leases with sub-4-second failover.
5. **Observability & FinOps**: 12-panel Grafana dashboard, OpenTelemetry W3C distributed tracing, and realistic cloud unit economics modeling.
6. **Zero Cost**: Built entirely within free-tier grants with an active $50 budget alert guardrail.
