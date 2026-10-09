# BurstOps Portal — Microsoft Azure Management Console

BurstOps Portal is an authentic Microsoft Azure Portal clone (`https://portal.azure.com/#home`) branded as **BurstOps Portal** for managing and monitoring the Layer-7 Elastic Burst Gateway on Microsoft Azure.

---

## Features

- **Azure Portal UI Clone**:
  - **48px Dark Top Bar**: Hamburger menu, custom BurstOps mark, wide global search (`G+/`), live gateway mode pill (Baseline `<80%` / Burst `≥80%`), Cloud Shell terminal jump, notification drawer, settings modal, help modal, user profile.
  - **Collapsible Left Rail**: `+ Create a resource`, `Home`, `Dashboard`, `All resources`, and `Favorites` (Gateway, Monitor, Cost Management, Load Test, Activity log, Service health).
  - **Breadcrumbs & Command Bar**: Blade titles, resource subtitle, and Azure command toolbar (`Refresh`, `Simulate Burst`, `Recover Baseline`, `Grafana`, `Jaeger`, `Locust`, `Prometheus`, `Feedback`).
  - **Theme Support**: Seamless toggle between Azure Dark and Azure Light themes.
- **Blades & Pages**:
  - **Home Blade (`#home`)**: Azure services grid, Recent resources table, Subscriptions/Resource group navigation tiles, and Telemetry tool cards.
  - **Gateway Overview Blade**: Collapsible Essentials panel, 4 KPI tiles (CPU observed %, Routing mode, PI continuous deflection ratio, p95 upstream latency), and tabbed views.
  - **Azure Monitor Metrics Blade**: Time-range selector (5m / 15m / 1h), interactive SVG time-series charts with 80% burst and 60% recovery hysteresis threshold lines, requests by target, deflection ratio, and latency.
  - **Cost Management (FinOps) Blade**: Amortized container cost ($0.000008/req) vs serverless cost ($0.000046/req), 5.76x premium multiplier, 28.55 RPS breakeven gauge, and HPA-lag cost savings.
  - **Load Test Controller Blade**: Preserves 1-click cloud demonstration buttons (*Action 1: Generate Traffic / Simulate Burst* and *Action 2: Recover to Baseline*), deterministic CPU-sim knobs (Port 8002 slider & presets), live `/calculate` probe tester, Sieve mathematical parity verification canaries (168 primes, sum 76,127), and Cloud Shell streaming execution log console.
  - **Activity Log Blade**: Client-side audit log with filter chips recording state machine transitions.
  - **Service Health Blade**: Health status matrix for Gateway, AKS backend pods, Azure Functions, Redis lock backplane, and Prometheus scraper.
  - **All Resources Blade**: Searchable catalog of all deployed Azure resources.

---

## Environment Variables & Configuration

The frontend communicates with the gateway through a Vite dev-server proxy in development and supports environment variable overrides:

| Variable | Description | Default |
|---|---|---|
| `VITE_GATEWAY_URL` | Base URL of the BurstOps Layer-7 Gateway | `http://burstops-cloud-ga3cvf.centralindia.cloudapp.azure.com` |
| `VITE_CPUSIM_URL` | Base URL of the CPU Simulator service | `http://localhost:8002` |

> **In-Browser Runtime Override**: You can also override the Gateway API URL dynamically inside the portal at any time by clicking the **Settings (gear)** icon in the top navigation bar.

---

## Getting Started

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Run Development Server
```bash
npm run dev
```
The portal will be available at `http://localhost:5173`.

### 3. Production Build
```bash
npm run build
```
Build output is generated in `frontend/dist/`.

### 4. Preview Production Build Locally
```bash
npm run preview
```
