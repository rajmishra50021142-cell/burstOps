# BurstOps — Step-by-Step Verification Guide

This guide gives you an exact, copy-pasteable walkthrough to verify the entire **BurstOps** project step by step:
1. **Locally** (100% operational right now without cloud dependency)
2. **On Microsoft Azure** (how to reactivate and verify against the live cloud Function)
3. **Observability & Architecture Graphs** (how to view real-time traffic graphs in Grafana and Azure Portal)

---

## Table of Contents

1. [Diagnosis: Why Did Your Azure Subscription Expire & Graphs Stop?](#1-diagnosis-why-did-your-azure-subscription-expire--graphs-stop)
2. [Part A — Local Verification Walkthrough (Run This First)](#2-part-a--local-verification-walkthrough-run-this-first)
   - [Step 1: Turn On the Containers](#step-1-turn-on-the-containers)
   - [Step 2: Run the 89-Test Automated Suite](#step-2-run-the-89-test-automated-suite)
   - [Step 3: Verify Baseline Routing (K8s)](#step-3-verify-baseline-routing-k8s)
   - [Step 4: Simulate a Traffic Surge & Verify Burst Deflection](#step-4-simulate-a-traffic-surge--verify-burst-deflection)
   - [Step 5: Verify Hysteresis & Recovery Below 60%](#step-5-verify-hysteresis--recovery-below-60)
   - [Step 6: View the Live Architecture Graph in Grafana](#step-6-view-the-live-architecture-graph-in-grafana)
   - [Step 7: Verify Multi-Replica Scale & Redis Backplane](#step-7-verify-multi-replica-scale--redis-backplane)
   - [Step 8: Turn Off Containers When Done](#step-8-turn-off-containers-when-done)
3. [Part B — Azure Cloud Verification (Once Reactivated)](#3-part-b--azure-cloud-verification-once-reactivated)
   - [Step 1: Check Azure Subscription State](#step-1-check-azure-subscription-state)
   - [Step 2: How to Reactivate the Subscription](#step-2-how-to-reactivate-the-subscription)
   - [Step 3: Point Local Gateway to Azure Function via `.env.azure`](#step-3-point-local-gateway-to-azure-function-via-envazure)
   - [Step 4: View the Live Cloud Graph in Application Insights](#step-4-view-the-live-cloud-graph-in-application-insights)
4. [What Each Output Proves (The "Canary" Numbers)](#4-what-each-output-proves-the-canary-numbers)

---

## 1. Cloud Architecture & Subscription Status

### Active Azure Subscription
- **Subscription Name**: `Azure for Students`
- **Subscription ID**: `c6e32bdf-69dd-4451-8c44-7b35c5ad187b`
- **Subscription State**: `Enabled`
- **Location**: `centralindia`
- **Resource Group**: `rg-burstops-prod`

### Option A / B Cost Discipline (Zero Waste)
To prevent draining student credits, we do NOT run an expensive AKS cluster or VMSS node pool 24/7 on Azure ($30+/month). Instead:
- **Baseline Cluster**: Runs locally in Docker Compose as high-fidelity Kubernetes-equivalent pods with Nginx VIP, cAdvisor, and Prometheus.
- **Serverless Burst Target**: Runs live on **Azure Flex Consumption Function** (`func-burstops-live`), guarded by Application Insights daily caps (0.15 GB/day) and a $50 budget alert.
- **Result**: Complete end-to-end cloud burst capability with **$0 fixed cost** (1,000,000 free monthly executions).

---

## 2. Part A — Local Verification Walkthrough (Run This First)

The local stack is a complete, authentic stand-in for the Kubernetes cluster and cloud architecture. It runs 100% offline at $0 cost.

### Step 1: Turn On the Containers
Turn on the stopped containers:
```bash
docker compose start
```
Wait 5 seconds, then check status:
```bash
docker compose ps
```
**Expected Output**: All 10 services should show `Up`:
- `burstops-gateway-1` (port 8080)
- `burstops-backend-vip` (port 8000)
- `burstops-backend-1` & `burstops-backend-2`
- `burstops-dummy-serverless-1` (port 8001)
- `burstops-cpu-sim-1` (port 8002)
- `burstops-cadvisor` (port 8082)
- `burstops-prometheus-1` (port 9090)
- `burstops-grafana-1` (port 3000)
- `burstops-locust-1` (port 8089)

---

### Step 2: Run the 89-Test Automated Suite
Run the comprehensive pytest suite to verify all mathematical and architectural invariants:
```bash
.venv/bin/pytest tests/ -q
```
**Expected Output**:
```
89 passed in 0.5s
```
* **Proves**: Hysteresis state machine, HMAC signatures, PI controller math, FinOps unit economics, Redis leader lease, and OpenTelemetry trace propagation all pass.

---

### Step 3: Verify Baseline Routing (K8s)
Under normal load, all traffic should route to the Kubernetes-shaped backend replicas.

```bash
# 1. Check health
curl -s http://localhost:8080/health
```
**Expected Output**:
```json
{"mode": "baseline", "last_cpu": 0.0}
```

```bash
# 2. Execute a calculation request
curl -s http://localhost:8080/calculate
```
**Expected Output**:
```json
{
  "source": "k8s",
  "impl": "dummy-backend",
  "hostname": "a7c7fd3610c0",
  "prime_count": 168,
  "prime_sum": 76127
}
```
* Run the `curl` command a second time: notice the `hostname` flips to `8571354c2921`. This proves the Nginx VIP is actively round-robin load-balancing between both backend replicas!

---

### Step 4: Simulate a Traffic Surge & Verify Burst Deflection
Simulate cluster CPU spiking to 95% using `cpu-sim`:

```bash
# 1. Command CPU simulator to target 95%
curl -X POST 'http://localhost:8002/set?pct=95'

# 2. Wait 35 seconds (Prometheus 30s rate window + 5s glide)
sleep 35

# 3. Check health — should flip to "burst"
curl -s http://localhost:8080/health
```
**Expected Output**:
```json
{"mode": "burst", "last_cpu": 92.1}
```

Now execute requests during the burst window:
```bash
curl -s http://localhost:8080/calculate
```
**Expected Output**:
```json
{
  "source": "serverless",
  "impl": "dummy-serverless",
  "hostname": "f08537be0c62",
  "prime_count": 168,
  "prime_sum": 76127,
  "injected_latency_ms": 110.6,
  "cold_start": true
}
```
* **Proves**: The gateway detected CPU $\ge 80\%$, entered `BURST` mode, signed the request with HMAC-SHA256, and deflected it to serverless.

---

### Step 5: Verify Hysteresis & Recovery Below 60%
Simulate traffic calming down:

```bash
# 1. Set CPU to 20%
curl -X POST 'http://localhost:8002/set?pct=20'

# 2. Wait 35 seconds
sleep 35

# 3. Check health — should recover to "baseline"
curl -s http://localhost:8080/health
```
**Expected Output**:
```json
{"mode": "baseline", "last_cpu": 22.3}
```

```bash
# 4. Verify traffic is back on k8s
curl -s http://localhost:8080/calculate
```
**Expected Output**:
```json
{"source": "k8s", "impl": "dummy-backend", ...}
```
* **Proves**: The gateway stayed deflected during the dead band (80% down to 60%) to prevent flapping, and safely returned to baseline once CPU dropped below 60%.

---

### Step 6: View the Live Architecture Graph in Grafana
You can view real-time architectural graphs and telemetry panels in your web browser:

1. Open your browser and go to: **[http://localhost:3000](http://localhost:3000)**
2. Log in with:
   - **Username**: `admin`
   - **Password**: `burstops`
3. Click on the dashboard: **"BurstOps — Burst Routing Monitor"**
4. You will see **12 live panels**:
   - **Routing Mode**: Shows 0 (Baseline) or 1 (Burst).
   - **Cluster CPU vs. Thresholds**: Real-time CPU curve with visual 80% (Burst) and 60% (Recovery) lines.
   - **Requests by Destination**: Live graph showing requests splitting between `k8s` and `serverless`.
   - **Deflection Ratio ($r$)**: Displays the continuous PI controller output (0.0 to 1.0).
   - **Upstream Latency (p95)**: Latency comparison between local pods vs. serverless cold/warm starts.
   - **FinOps Metrics**: Live cost accumulation and the 28.55 RPS breakeven gauge.

---

### Step 7: Verify Multi-Replica Scale & Redis Backplane
To test multiple gateway instances coordinating without split-brain:

```bash
# 1. Launch 3 gateway replicas with the Redis backplane overlay
docker compose -f docker-compose.yml -f docker-compose.scale.yml up -d --scale gateway=3

# 2. Inspect leader election on all 3 replicas
for i in 1 2 3; do
  PORT=$(docker compose -f docker-compose.yml -f docker-compose.scale.yml port --index=$i gateway 8080 | cut -d: -f2)
  echo "--- Replica on port $PORT ---"
  curl -s http://localhost:$PORT/metrics | grep -E '^gateway_is_leader'
done
```
**Expected Output**: Exactly **one** replica outputs `gateway_is_leader 1.0`, while the other two output `gateway_is_leader 0.0`.
* **Proves**: Redis Lua Compare-And-Set (CAS) elected a single leader to poll Prometheus, while followers receive state via pub/sub with zero I/O on the request path.

---

### Step 8: Turn Off Containers When Done
To pause the stack without deleting container state or data:
```bash
docker compose stop
```
*(When you want to start them again later, simply run `docker compose start`!)*

---

## 3. Part B — Live Azure Cloud Burst Verification (Active)

The live Azure cloud backend is fully deployed and operational in `rg-burstops-prod` (`centralindia`). The local gateway is already wired to it via `.env.azure`.

### Step 1: Verify Subscription State
```bash
az account show --query '{name:name, state:state, id:id}' -o table
```
**Expected Output**:
```
Name                State    Id
------------------  -------  ------------------------------------
Azure for Students  Enabled  c6e32bdf-69dd-4451-8c44-7b35c5ad187b
```

---

### Step 2: Direct Test Against Live Azure Function
Verify the Azure Function endpoint directly across the public internet:

```bash
KEY=$(az functionapp keys list -g rg-burstops-prod -n func-burstops-live --query 'functionKeys.default' -o tsv)
curl -s -i "https://func-burstops-live.azurewebsites.net/api/calculate?code=$KEY"
```
**Expected Output**:
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"source": "serverless", "impl": "azure-function", "prime_count": 168, "prime_sum": 76127}
```
* **Security Check**: Omitting the key or HMAC signature returns `HTTP 401 Unauthorized`.

---

### Step 3: Trigger Live Burst Deflection Through Local Gateway
Now test the end-to-end flow where the local gateway automatically deflects traffic to Azure:

```bash
# 1. Trigger simulated CPU surge to 95%
curl -X POST 'http://localhost:8002/set?pct=95'

# 2. Wait 20 seconds for the gateway to enter burst mode
sleep 20
curl -s http://localhost:8080/health
# Expected: {"mode":"burst","last_cpu":...}

# 3. Send requests to the local gateway
curl -i http://localhost:8080/calculate
```
**Expected Output**:
```http
HTTP/1.1 200 OK
content-type: application/json

{"source": "serverless", "impl": "azure-function", "instance_id": "local", "prime_count": 168, "prime_sum": 76127, "cold_start": false}
```
* **Notice**: `"impl": "azure-function"`. The request entered `localhost:8080`, was cryptographically signed with HMAC-SHA256, forwarded to Azure in `centralindia`, and processed by the cloud function!

---

### Step 4: Verify Recovery Back to Local Kubernetes
```bash
# 1. Reset CPU to 20%
curl -X POST 'http://localhost:8002/set?pct=20'

# 2. Wait 20 seconds
sleep 20
curl -s http://localhost:8080/health
# Expected: {"mode":"baseline","last_cpu":...}

# 3. Send request — traffic automatically returns to local cluster
curl -i http://localhost:8080/calculate
```
**Expected Output**:
```http
HTTP/1.1 200 OK
content-type: application/json

{"source":"k8s","impl":"dummy-backend","hostname":"28b379017faf","prime_count":168,"prime_sum":76127}
```

---

### Step 5: Visual Proofs & Architecture Diagrams

#### 1. Azure Portal — Overall Structure Diagram (Resource Visualizer)
To see the full cloud architecture diagram rendered natively by Azure:
1. Open the **[Azure Portal](https://portal.azure.com)**.
2. Search for **Resource groups** and click **`rg-burstops-prod`**.
3. In the left navigation menu under **Settings**, click **Resource visualizer**.
4. Azure will display an interactive visual topology diagram connecting:
   - **`func-burstops-live`** (Function App)
   - **`plan-burstops-3l8y5t`** (Flex Consumption Plan)
   - **`stburstops3l8y5t`** (Storage Account)
   - **`appi-burstops-3l8y5t`** (Application Insights)
   - **`log-burstops-3l8y5t`** (Log Analytics Workspace)

#### 2. Azure Portal — Application Map (Visual Traffic Flow)
1. In the Azure Portal, open **`appi-burstops-3l8y5t`**.
2. In the left navigation under **Investigate**, click **Application Map**.
3. You will see the visual flow graph showing real incoming traffic calls, request rate, and latency circles connecting to the function.

#### 3. Azure Portal — Live Metrics (Real-Time Streaming)
1. In `appi-burstops-3l8y5t`, click **Live Metrics** under **Investigate**.
2. Run a loop of requests in your terminal:
   ```bash
   for i in {1..20}; do curl -s http://localhost:8080/calculate > /dev/null; done
   ```
3. Watch the Live Metrics charts spike in real time showing incoming requests/sec, request duration, and serverless compute memory.

#### 4. Local Grafana Dashboard — Routing & FinOps Monitor
1. Open **[http://localhost:3000](http://localhost:3000)** (admin / `burstops`).
2. Open dashboard **"BurstOps — Burst Routing Monitor"**.
3. View the 12 real-time panels showing:
   - Routing mode transition (0 = Baseline, 1 = Burst)
   - Cluster CPU curve crossing 80% and 60%
   - Traffic deflection split (`k8s` vs `serverless`)
   - Burst premium accrued (FinOps economics)
   - Breakeven overflow RPS gauge (28.55 RPS)

---

## 4. What Each Output Proves (The "Canary" Numbers)

| Output / Value | Why It Matters |
|---|---|
| `prime_count: 168` / `prime_sum: 76127` | **Work Canary**: Sieve of Eratosthenes over 2..1000. Proves that both the Kubernetes backend and the Azure Function execute real, equivalent compute work. |
| `impl: "dummy-backend"` vs `impl: "azure-function"` | Proves which infrastructure layer executed the request. |
| Flip at ~30–35 seconds | Reflects the 30-second `rate(container_cpu...[30s])` smoothing window—proves the gateway honors genuine sliding-window PromQL metrics rather than instantaneous noisy spikes. |
| Recovery strictly below 60% | Proves the **dead band** (60%–80%) prevents flapping. If CPU is 72%, the gateway remains in its current state. |
| `gateway_breakeven_overflow_rps 28.55` | The FinOps unit economics threshold. Deflection below 28.55 RPS is cheaper than provisioning another Kubernetes node; above 28.55 RPS, scaling out nodes is cheaper. |
