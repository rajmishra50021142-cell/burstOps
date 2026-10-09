# BurstOps Interactive Demo Website — Render Deployment & Demonstration Manual

This document provides complete, beginner-friendly instructions for running the **BurstOps Interactive Demo Website** locally, testing it with automated suites, pushing it to your GitHub repository, and deploying it as a **single Render Web Service**.

---

## 1. Executive Overview

The BurstOps Interactive Demo Website is a presentation control panel designed for university project evaluations. It replaces manual terminal commands with two primary actions:

1. **Button 1: Generate Traffic / Simulate Burst**
   - Triggers real, bounded traffic through the live Azure deployment via the public Ingress and in-cluster load generator.
   - Pushes backend CPU $> 80\%$, engaging the gateway's PI proportional deflection controller.
   - Monitors live deflection to the Azure Function (`source: serverless`, `impl: azure-function`, `prime_count: 168`, `prime_sum: 76127`).
   - Keeps the burst state active so you can show Grafana and Azure Portal during your evaluation.
2. **Button 2: Recover to Baseline**
   - Stops the active load generator.
   - Allows the cluster to cool down below the $60\%$ recovery threshold naturally (honoring the $20\%$ anti-flapping dead band).
   - Verifies recovery back to Kubernetes (`source: k8s`, `impl: dummy-backend`).

---

## 2. Architecture & How the Cloud Trigger Works

### Single-Service Architecture on Render
The application is structured to run as a **single Render Web Service** (zero extra microservices or databases required):

```
                       User Browser / Evaluator
                                  │
                                  ▼
               ┌─────────────────────────────────────┐
               │    Render Web Service (Port $PORT)   │
               │                                     │
               │  ┌───────────────────────────────┐  │
               │  │  React + Vite Frontend (SPA)  │  │
               │  │  (Served from frontend/dist)  │  │
               │  └───────────────┬───────────────┘  │
               │                  │ Same-origin API  │
               │                  ▼                  │
               │  ┌───────────────────────────────┐  │
               │  │     FastAPI Backend Engine    │  │
               │  │     (/api/demo/* endpoints)   │  │
               │  └───────────────┬───────────────┘  │
               └──────────────────┼──────────────────┘
                                  │ Public HTTP Calls
                                  ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │               Live Azure Cloud Cluster (centralindia)           │
 │                                                                 │
 │   1. In-Cluster Load Generator: POST /locust/swarm (20 users)   │
 │   2. Sustained Traffic Workers: POST /calculate                 │
 │   3. State Machine Monitoring : GET  /health                    │
 │   4. Serverless Overflow      : Azure Function Flex Consumption │
 └─────────────────────────────────────────────────────────────────┘
```

### Why this design requires ZERO local dependencies:
- **No local `kubectl` required on Render**: Load generation is commanded through the verified public Ingress endpoints of the existing Azure deployment (`/locust/swarm` and `/calculate`).
- **No Azure Admin Credentials required on Render**: Traffic is public HTTP traffic evaluated by the gateway itself. The gateway signs requests with HMAC-SHA256 internally when deflecting to Azure Functions.
- **No Mac terminal dependencies**: You do not need to keep your laptop terminal open during the presentation.

---

## 3. How to Run & Test the Application Locally

### A. Run Automated Tests
All automated tests run against a fast, high-fidelity **Mock Adapter** that does not touch live Azure resources or generate network traffic:

```bash
# 1. Activate your virtual environment
source .venv/bin/activate

# 2. Run the 13 demo service tests
PYTHONPATH=. pytest tests/test_demo_service.py -v

# 3. Run the complete test suite (all 101 tests)
PYTHONPATH=. pytest tests/ -q
```

### B. Build the Frontend Locally
```bash
cd frontend
npm install
npm run build
cd ..
```
The production bundle is compiled into `frontend/dist`.

### C. Run the Local Server (Single Service Mode)
You can test the exact production single-service mode locally on port 8000:

```bash
# Run in mock mode (safe offline testing):
DEMO_MODE=mock PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Or run in live cloud mode (talks to real Azure):
DEMO_MODE=cloud PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 4. Deploying to Render (Step-by-Step)

Follow these exact steps to deploy to Render:

### Step 1: Commit and Push to GitHub
```bash
git add backend/ frontend/ tests/test_demo_service.py render.yaml requirements-demo.txt .env.example build.sh RENDER_DEPLOYMENT.md
git commit -m "feat: implement interactive burstops demo website and single-service packaging"
git push origin main
```

### Step 2: Create Web Service on Render
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** $\to$ **Web Service**.
3. Select your repository: `rajmishra50021142-cell/burstOps`.
4. Configure the service settings:
   - **Name**: `burstops-demo`
   - **Language / Runtime**: `Python 3`
   - **Region**: `Oregon (US West)` (or your preferred region)
   - **Branch**: `main`
   - **Build Command**:
     ```bash
     pip install -r requirements-demo.txt && cd frontend && npm install && npm run build && cd ..
     ```
   - **Start Command**:
     ```bash
     uvicorn backend.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type**: `Free` or `Starter`

### Step 3: Configure Environment Variables in Render
In the **Environment** section of your Render Web Service, add the following non-sensitive variables (or verify them against `.env.example`):

| Variable Name | Recommended Value | Explanation |
|---|---|---|
| `DEMO_MODE` | `cloud` | Set to `cloud` for live Azure experiment. |
| `GATEWAY_BASE_URL` | `http://burstops-cloud-ga3cvf.centralindia.cloudapp.azure.com` | Public gateway endpoint on Azure. |
| `LOCUST_INGRESS_URL` | `http://burstops-cloud-ga3cvf.centralindia.cloudapp.azure.com/locust` | Public ingress route to in-cluster load generator. |
| `GRAFANA_URL` | `http://burstops-cloud-ga3cvf.centralindia.cloudapp.azure.com/grafana/` | In-cluster Grafana dashboard URL. |
| `PROMETHEUS_URL` | `http://burstops-cloud-ga3cvf.centralindia.cloudapp.azure.com/metrics` | Raw Prometheus metrics endpoint. |
| `AZURE_SUBSCRIPTION_ID`| `980e5d74-260c-49bc-ba07-2343e710859d` | Your Azure subscription ID for portal links. |
| `AZURE_RESOURCE_GROUP` | `rg-burstops-prod` | Target resource group. |
| `AZURE_AKS_CLUSTER` | `aks-burstops-ga3cvf` | Managed Kubernetes cluster name. |
| `AZURE_FUNCTION_APP` | `func-burstops-cloud-ga3cvf` | Serverless Function App name. |
| `AZURE_APP_INSIGHTS` | `log-burstops-ga3cvf` | Application Insights workspace name. |
| `MAX_RUN_DURATION_SECONDS` | `120` | Safety hard cap to auto-recover if left unattended. |
| `RECOVERY_TIMEOUT_SECONDS` | `60` | Maximum wait time for CPU to decay below 60%. |
| `COOLDOWN_SECONDS` | `5` | Anti-hammering cooldown between runs. |

> **Note on Credentials**: No Azure API keys, passwords, or HMAC secrets are needed on Render. The website operates through public ingress endpoints, preserving security.

### Step 4: Deploy
Click **Create Web Service**. Render will install Python dependencies, compile the React bundle with Vite, and launch Uvicorn. Once the deployment finishes, Render provides your public URL (e.g. `https://burstops-demo.onrender.com`).

---

## 5. Live Demonstration Runbook for Evaluators

Here is the exact script to follow during your demonstration:

### 1. Initial State (Baseline)
- Open your Render website.
- Click the prominent **Open Grafana Dashboard** button (opens in a new tab).
- Show the evaluator:
  - Routing Mode is **0 (Baseline)**.
  - Deflection Ratio is **0.00**.
  - $100\%$ of traffic is handled by local Kubernetes pods.

### 2. Trigger the Burst
- Return to your website tab.
- Click **Action 1: Generate Traffic / Simulate Burst**.
- Watch the live execution console stream real-time logs:
  - In-cluster Locust swarm engaged (20 concurrent users).
  - Telemetry polls display backend CPU ramping: $15\% \to 45\% \to 78\% \to 92\%$.
- Once CPU exceeds $80\%$:
  - Status changes to **Burst Detected (CPU $\ge$ 80%)** $\to$ **Serverless Deflection Verified**.
  - Sieve Canary card updates with real telemetry:
    - `source: serverless`
    - `impl: azure-function`
    - `primes: 168 / sum: 76127`
- Switch to Grafana tab to show:
  - Routing mode flipped to **1 (Burst)**.
  - Deflection ratio rose to $0.40 - 0.70$.
  - Upstream latency histogram shows split between local pods and serverless executions.

### 3. Recover to Baseline
- Return to the website.
- Click **Action 2: Recover to Baseline**.
- Watch the console:
  - Active traffic generation ceases.
  - Cluster cools down through the dead band ($80\% \to 60\%$).
- Once CPU decays below $60\%$:
  - Status changes to **Baseline Verified (Self-Healed)**.
  - Recovery canary confirms return: `source: k8s`, `impl: dummy-backend`.
- Notice that **both the burst canary and recovery canary remain visible side-by-side** for evaluator discussion.

---

## 6. Troubleshooting & Operational Notes

- **Render Free Tier Cold Starts**: On the Render free tier, web services spin down after 15 minutes of inactivity. When opening the site for the presentation, allow 30–50 seconds for the initial wake-up.
- **Cooldown Safeguard**: A 5-second cooldown protects the gateway from rapid re-triggering. If clicked immediately, a friendly badge asks you to wait a moment.
- **Automated Safety Cap**: If you forget to click "Recover to Baseline", the backend will automatically initiate recovery after 120 seconds to prevent unnecessary load on your Azure subscription.
