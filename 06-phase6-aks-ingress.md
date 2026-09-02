# PROMPT 06 — Phase 6: AKS migration and ingress

> Paste this entire file to the coding agent as its task. It is self-contained.

## Your role

You are working on **BurstOps**, a Layer-7 gateway that compensates for
Kubernetes HPA provisioning lag. A background poller queries Prometheus every 2s
for cluster CPU; at ≥80% the gateway deflects `/calculate` traffic to an Azure
Function instead of Kubernetes, and returns to Kubernetes below 60%. The 60/80
hysteresis band exists to stop it flapping.

Phase 5's Terraform created the AKS cluster, ACR, Key Vault and Function App.
This task gets BurstOps actually running on AKS behind a TLS ingress, with
Prometheus feeding the gateway's CPU query.

The subscription is **cost-minimized (student / free credits)**. That single
constraint decides the ingress choice in §5, so read that section before writing
any manifest.

## What already exists — extend it, don't recreate it

`k8s/` already contains two manifests written in anticipation of this phase:

- **`backend-deployment.yaml`** — `Deployment` `burstops-backend`, namespace
  `burstops`, 2 replicas, image placeholder
  `burstopsacr.azurecr.io/burstops-backend:v1`, requests `250m`/`128Mi`, limits
  `1000m`/`256Mi` (matched to the Compose `cpus: "1.0"` cap on purpose), probes on
  `GET /health` port 8000, pod label `burstops-namespace: burstops`.
- **`backend-service.yaml`** — `LoadBalancer` Service `burstops-backend`,
  port 8000 → targetPort 8000.

**Do not rewrite, reformat, or "clean up" either file.** Keep the namespace
`burstops` and the `burstops-namespace: burstops` pod label exactly as they are —
Prometheus relabeling depends on that label surviving. If you believe one of them
must change, say so and wait (§8).

## Scope

```
k8s/
├── namespace.yaml            # if it doesn't already exist — verify first
├── gateway-deployment.yaml   # new
├── gateway-service.yaml      # new — ClusterIP, needed by the Ingress
├── ingress.yaml              # new
├── kustomization.yaml        # new — image overrides without editing existing files
└── gateway-secret.example.yaml  # template only, never a real secret
docs/
└── phase6-runbook.md         # image build/push/pull path, deploy, verify, teardown
```

## 1. Verify before you write anything

```bash
ls -la k8s/; cat k8s/backend-deployment.yaml k8s/backend-service.yaml
grep -n -E 'K8S_UPSTREAM|FUNCTION_UPSTREAM|FUNCTION_KEY|GATEWAY_HMAC_SECRET|PROMETHEUS_URL' gateway/gateway_entrypoint.py
grep -n -E 'PROM_QUERY|POLL_INTERVAL|BURST_THRESHOLD|RECOVERY_THRESHOLD' gateway/gateway.py
cat gateway/Dockerfile dummy-backend/Dockerfile

kubectl config current-context
kubectl get nodes -o wide
kubectl get ns
kubectl top nodes 2>&1 | head          # metrics-server present?
cd terraform && terraform output && cd ..
az acr repository list -n <acr-name> -o table
```

Report: the exact env var names `gateway_entrypoint.py` patches (these are the
names your Deployment must set — the shim reads specific names and nothing else),
the current allocatable CPU per node, whether a `burstops` Namespace object exists
anywhere in `k8s/`, and the Terraform outputs you will need (ACR login server, AKS
name, Function hostname, Key Vault name).

## 2. Read this before writing the gateway Deployment — the metric semantics change

This is the single most likely way Phase 6 silently fails, so work through it
before writing YAML.

The gateway runs this query, unchanged, and it is **not** patched by an env var —
`gateway_entrypoint.py` patches `PROMETHEUS_URL` but not the query itself:

```promql
avg(rate(container_cpu_usage_seconds_total{namespace="burstops"}[30s])) * 100
```

In Docker Compose, `namespace="burstops"` was a synthetic label that
`prometheus/prometheus.yml` stamped onto exactly two backend containers. The
average was therefore over two series and cleanly tracked backend load.

In real Kubernetes, `namespace` is a genuine cAdvisor label meaning "the namespace
this pod is in". So `{namespace="burstops"}` matches **everything in the namespace**:
both backend containers, the gateway's own container, any sidecars, and — depending
on your Prometheus config — pod-level aggregate series where `container=""`. `avg`
collapses all of them.

Do the arithmetic. Backends saturated at 0.85 cores each, gateway near-idle at
0.02, plus two pod-level duplicates:

```
avg(0.85, 0.85, 0.85, 0.85, 0.02, 0.02) = 0.573  ->  57%
```

The gateway would report 57% while the backends are pinned, and **would never
cross the 80% burst threshold**. BurstOps would appear to work and never actually
burst.

Measure it rather than assume. After Prometheus is running (§4):

```bash
kubectl -n monitoring port-forward svc/<prometheus-svc> 9090:9090 &
curl -s localhost:9090/api/v1/query --data-urlencode \
  'query=count by (pod, container) (container_cpu_usage_seconds_total{namespace="burstops"})' | python3 -m json.tool
curl -s localhost:9090/api/v1/query --data-urlencode \
  'query=avg(rate(container_cpu_usage_seconds_total{namespace="burstops"}[30s])) * 100' | python3 -m json.tool
```

If the series count is greater than the number of backend containers, you have the
dilution problem. **Stop and present these options to the user; do not pick one
yourself:**

- **(a) Put the gateway in a different namespace** (e.g. `burstops-system`), leaving
  only backend pods in `burstops`, plus a Prometheus `metric_relabel_config`
  dropping series with an empty `container` label. Keeps `gateway.py` untouched.
  Note this contradicts the handoff's instruction that the gateway Deployment use
  namespace `burstops` — which is exactly why it needs a decision, not a guess.
- **(b) Keep the gateway in `burstops`** and add a Prometheus recording rule plus a
  relabel that narrows what carries `namespace="burstops"` to backend containers
  only, mirroring what the Compose config did.
- **(c) Change `PROM_QUERY` in `gateway.py`** to something namespace-and-pod
  specific, e.g.
  `avg(rate(container_cpu_usage_seconds_total{namespace="burstops",pod=~"burstops-backend-.*",container!=""}[30s])) * 100`.
  Cleanest semantically, but `gateway.py` is the protected spec file and the
  constant is not env-patchable, so it requires explicit permission. If granted,
  the change must also be reflected in `prometheus/prometheus.yml`'s Compose setup
  so local and AKS behaviour stay identical, and `tests/test_hysteresis.py` must
  still pass untouched (it tests `RoutingState`, not the query, so it should).

Recommend (a) as the least invasive, but let the user choose.

## 3. `gateway-deployment.yaml`

```yaml
replicas: 1   # NOT more - see the note below
```

**One replica, deliberately.** `RoutingState` is a single in-memory Python object.
With N replicas, each polls Prometheus and decides independently, so during a
transition they disagree and traffic splits inconsistently — the split-brain
problem Upgrade B (Redis backplane) exists to solve. Put that reasoning in a YAML
comment so nobody scales it up casually. Once Upgrade B lands, this becomes 2–3.

Required content:

- Namespace per §2's decision. Pod labels must not disturb the existing
  `burstops-namespace: burstops` convention on the backend.
- Image `<acr-login-server>/burstops-gateway:v1`, `imagePullPolicy: IfNotPresent`.
  No imagePullSecret — Phase 5 granted the kubelet identity `AcrPull`.
- Container port 8080.
- Probes: `readinessProbe` and `livenessProbe` on `GET /health`, port 8080. Use a
  `startupProbe` too — the poller needs a cycle or two before `/health` is
  meaningful. Keep `failureThreshold` generous on liveness: `/health` returning
  slowly must not trigger a restart loop mid-burst.
- Resources: requests `100m`/`128Mi`, limits `500m`/`256Mi`. Justify against §1's
  allocatable-CPU number, since a single `Standard_B2s` node also runs both
  backend replicas and the system pods.
- Env from a Secret for `GATEWAY_HMAC_SECRET` and `FUNCTION_KEY` via
  `secretKeyRef`. Plain env for the rest.
- `securityContext`: `runAsNonRoot: true`, a numeric `runAsUser`,
  `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`,
  `capabilities.drop: ["ALL"]`, `seccompProfile.type: RuntimeDefault`. If
  `readOnlyRootFilesystem` breaks uvicorn, add an `emptyDir` at `/tmp` rather than
  dropping the setting.
- Prometheus discovery: annotate `prometheus.io/scrape: "true"`,
  `prometheus.io/port: "8080"`, `prometheus.io/path: "/metrics"` — and if you use
  the kube-prometheus-stack (§4), add a `ServiceMonitor` instead, since that chart
  ignores those annotations by default. Do whichever your Prometheus actually
  honours, and verify the target appears.

### Env vars — names are fixed by the shim

`gateway/gateway_entrypoint.py` imports `gateway.py` and patches its module-level
constants from specific environment variable names. Setting different names is a
silent no-op: the gateway would boot with its placeholder defaults and fail in a
confusing way. Confirm the exact names in §1 and use them:

| Env var | Value in AKS |
|---|---|
| `K8S_UPSTREAM` | `http://burstops-backend.burstops.svc.cluster.local:8000` |
| `FUNCTION_UPSTREAM` | `https://<func-app>.azurewebsites.net/api/calculate` |
| `PROMETHEUS_URL` | `http://<prom-svc>.<prom-ns>.svc.cluster.local:9090/api/v1/query` |
| `FUNCTION_KEY` | `secretKeyRef` → `burstops-gateway` / `function-key` |
| `GATEWAY_HMAC_SECRET` | `secretKeyRef` → `burstops-gateway` / `hmac-secret` |

Use the fully-qualified in-cluster DNS name for `K8S_UPSTREAM`, and keep the
`/api/v1/query` suffix on `PROMETHEUS_URL` — that is the shape `gateway.py`
expects.

Do not preserve `.env`'s `K8S_UPSTREAM=http://20.219.208.79:8000`. That bare IP is
a Compose-era artifact; inside the cluster the Service DNS name is the only correct
target. Mention in your report that you did not carry it over.

### The secret

Never commit real values. Ship `gateway-secret.example.yaml` with placeholders and
document the create command in the runbook, sourcing from Key Vault so the values
are never typed:

```bash
HMAC=$(az keyvault secret show --vault-name <kv> -n gateway-hmac-secret --query value -o tsv)
FKEY=$(az functionapp keys list -g rg-burstops-prod -n <func-app> --query 'functionKeys.default' -o tsv)
kubectl -n burstops create secret generic burstops-gateway \
  --from-literal=hmac-secret="$HMAC" \
  --from-literal=function-key="$FKEY" \
  --dry-run=client -o yaml | kubectl apply -f -
unset HMAC FKEY
```

Note in the runbook that the production upgrade is the Secrets Store CSI driver
with the Key Vault provider, which syncs directly and avoids a long-lived copy in
etcd. It is a paid-complexity, not paid-money, upgrade — mention it, don't build it
here unless asked.

## 4. In-cluster Prometheus

The gateway needs a Prometheus to query, and cost minimization rules out Azure
Monitor managed Prometheus (billed per ingested sample). Use the
`kube-prometheus-stack` Helm chart in a `monitoring` namespace with retention
trimmed to something small (24h matches the Compose setup) and modest resource
requests, since a single B2s node is already tight.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install kps prometheus-community/kube-prometheus-stack -n monitoring --create-namespace \
  --set prometheus.prometheusSpec.retention=24h \
  --set prometheus.prometheusSpec.resources.requests.cpu=100m \
  --set prometheus.prometheusSpec.resources.requests.memory=400Mi \
  --set grafana.enabled=true \
  --set alertmanager.enabled=false
```

If the chart will not fit on one node, say so with the eviction/pending evidence
and present the options (2 nodes, or a bare `prometheus` Deployment with a
hand-written scrape config) rather than silently disabling things.

Two things to verify, not assume: that the gateway's `/metrics` target is being
scraped and all six `gateway_*` metrics are present with the same names as
Compose, and §2's series-count query. Also re-provision the existing 6-panel
dashboard (`grafana/provisioning/dashboards/burstops.json`) into this Grafana with
a datasource whose **uid is `burstops-prometheus`** — every panel is hardcoded to
that uid and will show "datasource not found" otherwise.

## 5. Ingress — read this before writing `ingress.yaml`

The handoff mentions an Application Gateway. **Do not provision one.** An
`Application Gateway Standard_v2` bills a fixed hourly charge plus capacity units,
landing somewhere around $130–250/month — more than every resource in Phase 5's
table combined, on a subscription running on free credits. Confirm current pricing
if you want, but do not create one without the user explicitly asking.

Use **ingress-nginx** instead. It runs as a Deployment in the cluster and asks
Azure for one Standard Load Balancer plus one public IP (roughly $20–25/month
total, and AKS has already created a Load Balancer for the existing backend
`LoadBalancer` Service — see §6b). If the AKS **app routing add-on** (managed NGINX)
is available on this cluster version, it is an equally valid and slightly cheaper
choice; check, then pick one and say which.

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  --set controller.replicaCount=1 \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/azure-dns-label-name"=burstops-<suffix>
kubectl -n ingress-nginx get svc ingress-nginx-controller -w   # wait for EXTERNAL-IP
```

### Hostname: use the Azure-provided DNS label, not `nip.io`

That `azure-dns-label-name` annotation gives the public IP a real name:
`burstops-<suffix>.<region>.cloudapp.azure.com`. Prefer it over `nip.io` or
`sslip.io` for one specific reason: `cloudapp.azure.com` is on the Public Suffix
List, so Let's Encrypt treats each label as its own registered domain and applies
rate limits per-label. `nip.io` is one shared registered domain, so its
certificate-per-week budget is consumed by everyone on the internet using it, and
issuance intermittently fails for reasons that have nothing to do with your
cluster. Keep `nip.io` as a fallback only, and say in the runbook why.

### TLS via cert-manager

```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace \
  --set crds.enabled=true
```

Write two `ClusterIssuer`s and **use staging first**:

- `letsencrypt-staging` — `https://acme-staging-v02.api.letsencrypt.org/directory`
- `letsencrypt-prod` — `https://acme-v02.api.letsencrypt.org/directory`

Both with an `http01` solver on `class: nginx`. Prove the whole chain works
against staging (browser will warn about the untrusted root — that is the expected
staging behaviour, not a failure), then switch the Ingress annotation to prod and
delete the staging Secret so a fresh certificate is requested. Getting this
backwards burns the prod rate limit on debugging attempts.

HTTP-01 needs port 80 reachable from the internet for the duration of the
challenge, so do not add an IP allowlist until after the first certificate issues.

### ⚠ The gateway has no authentication — say this out loud before exposing it

`gateway.py` authenticates *outbound* to the Function with HMAC. It has **no
inbound authentication whatsoever**. Publishing it through an Ingress puts
`POST /calculate`, `/health` and `/metrics` on the public internet, where anyone
can drive the prime sieve at your two backend pods, push observed CPU over 80, and
make your Function App invoke on your credits. `/metrics` also leaks your
routing state and traffic volumes.

**Do not silently ship a public unauthenticated endpoint.** Present these and let
the user choose:

- **(i) No Ingress at all — recommended for a demo.** `kubectl port-forward` the
  gateway Service and drive it from your laptop. Zero exposure, zero Load Balancer
  cost, and every acceptance check below still works over `localhost`. The
  tradeoff: no TLS story and no shareable URL.
- **(ii) Ingress restricted by source IP.** Ship it, then add
  `nginx.ingress.kubernetes.io/whitelist-source-range: "<your-public-ip>/32"`
  after the certificate issues. Keeps the TLS demo and the shareable URL, closed to
  everyone else.
- **(iii) Ingress with basic auth** in front of everything via
  `nginx.ingress.kubernetes.io/auth-type: basic` and an `auth-secret`. Note this
  changes the wire contract for any client, including Locust, which then needs
  credentials.
- **(iv) Fully public.** Only if the user explicitly says so. If they do, at
  minimum keep `/metrics` off the Ingress by not routing that path, and add
  `nginx.ingress.kubernetes.io/limit-rps`.

Write the `ingress.yaml` for whichever they pick. Default to (ii) if they express
a preference for having the TLS/ingress path working but say nothing about access
control — and state in your report that you did.

### `ingress.yaml` content

- `ingressClassName: nginx` as a field, not the deprecated
  `kubernetes.io/ingress.class` annotation.
- `cert-manager.io/cluster-issuer: letsencrypt-staging` initially.
- Host = the `cloudapp.azure.com` name from above; `tls:` block with that host and
  `secretName: burstops-gateway-tls`.
- One rule: `path: /`, `pathType: Prefix`, backend
  `service: burstops-gateway`, `port: 8080`.
- Do **not** route to `burstops-backend` directly. Every request must traverse the
  gateway or the routing logic is bypassed and the demo proves nothing.
- `nginx.ingress.kubernetes.io/proxy-read-timeout: "60"` — a cold Azure Function
  invocation through the burst path can take several seconds, and nginx's 60s
  default is fine, but set it explicitly so it is not a mystery later.

## 6. Images, and `kustomization.yaml` instead of editing existing files

### 6a. Build in ACR, not locally

```bash
ACR=$(cd terraform && terraform output -raw acr_name)     # or acr_login_server, check outputs.tf
az acr build -r "$ACR" -t burstops-gateway:v1  --platform linux/amd64 ./gateway
az acr build -r "$ACR" -t burstops-backend:v1  --platform linux/amd64 ./dummy-backend
az acr repository show-tags -n "$ACR" --repository burstops-gateway -o table
az acr repository show-tags -n "$ACR" --repository burstops-backend -o table
```

`az acr build` builds server-side, which matters more than convenience: on an Apple
Silicon machine a local `docker build` produces `linux/arm64` images, AKS nodes are
`linux/amd64`, and the pod fails with `exec format error` — a confusing symptom for
an obviously-correct Dockerfile. `--platform linux/amd64` removes the whole class of
problem. If you must build locally, use `docker buildx build --platform linux/amd64`
and say so.

**Check the gateway Dockerfile's `CMD` before you build.** The image must start
`gateway_entrypoint.py`, not `gateway.py`. The shim is the only thing that reads
§3's environment variables into `gateway.py`'s module constants; if `CMD` runs
`uvicorn gateway:app` directly, every env var you set is inert and the gateway boots
with placeholder upstreams. If that is what the Dockerfile does, **stop and report
it** (§8) — the fix touches `gateway/`, which is out of scope here.

### 6b. `kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespace.yaml
  - backend-deployment.yaml
  - backend-service.yaml
  - gateway-deployment.yaml
  - gateway-service.yaml
  - ingress.yaml
images:
  - name: burstopsacr.azurecr.io/burstops-backend   # copy this string byte-for-byte
    newName: <acr-login-server>/burstops-backend    # from backend-deployment.yaml
    newTag: v1
  - name: burstopsacr.azurecr.io/burstops-gateway
    newName: <acr-login-server>/burstops-gateway
    newTag: v1
```

Three things to get right:

- The `images[].name` must match the existing placeholder **exactly**, including the
  `burstopsacr.azurecr.io` prefix. Kustomize matches on the literal string; a
  mismatch silently leaves the unreachable placeholder in place and the pod sits in
  `ImagePullBackOff`. Read the value out of `backend-deployment.yaml`, don't retype
  it from this prompt.
- **Do not set a top-level `namespace:` field.** It rewrites the namespace of every
  resource, which breaks §2 option (a) (gateway deliberately in a different
  namespace) and quietly overrides what the backend manifest already declares. Keep
  namespaces explicit inside each manifest.
- **Do not list `gateway-secret.example.yaml` in `resources:`.** It contains
  placeholders; applying it would overwrite the real Secret with garbage.

### 6c. The backend Service is a `LoadBalancer` — flag it, don't change it

`backend-service.yaml` is `type: LoadBalancer`, which gives the **backend** its own
public IP. That is two problems at once: another ~$4/month of public IP for nothing,
and an unauthenticated `burstops-backend:8000` reachable from the internet, bypassing
the gateway entirely. Anyone hitting it directly makes the routing demo meaningless
and can saturate the pods at will.

`ClusterIP` is the correct type once an Ingress fronts the gateway. But
`backend-service.yaml` is a file this prompt told you not to rewrite, so: **report
this, quote the current type, recommend `ClusterIP`, and wait.** If the user
approves, change only the `type:` line and nothing else.

## 7. Acceptance — run all of it, paste all output

```bash
# --- A. Namespace, secret, apply ---
kubectl apply -f k8s/namespace.yaml            # plus the gateway's ns if §2 chose (a)
# create the Secret per §3 (Key Vault sourced, never typed)
kubectl -n burstops get secret burstops-gateway -o jsonpath='{.data}' | tr ',' '\n' | cut -d'"' -f2
# ^ prints KEY NAMES ONLY. Never echo the values.

kubectl apply -k k8s/
kubectl -n burstops rollout status deploy/burstops-backend --timeout=180s
kubectl -n <gateway-ns> rollout status deploy/burstops-gateway --timeout=180s
kubectl get pods -A -o wide | grep -E 'burstops|monitoring|ingress-nginx|cert-manager'

# --- B. Nothing is Pending for lack of CPU (the B2s risk) ---
kubectl get pods -A --field-selector=status.phase=Pending
kubectl describe node | sed -n '/Allocated resources/,/^Events/p'

# --- C. Prometheus scrapes the gateway; the six metrics exist ---
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090:9090 &
curl -s localhost:9090/api/v1/targets | python3 -c 'import sys,json;[print(t["labels"].get("job"),t["health"],t.get("lastError","")) for t in json.load(sys.stdin)["data"]["activeTargets"]]'
curl -s localhost:9090/api/v1/label/__name__/values | tr ',' '\n' | grep gateway_

# --- D. §2's dilution check — MANDATORY, this is the phase's main trap ---
curl -s localhost:9090/api/v1/query --data-urlencode \
  'query=count by (pod, container) (container_cpu_usage_seconds_total{namespace="burstops"})' | python3 -m json.tool
curl -s localhost:9090/api/v1/query --data-urlencode \
  'query=avg(rate(container_cpu_usage_seconds_total{namespace="burstops"}[30s])) * 100' | python3 -m json.tool

# --- E. Baseline behaviour through the gateway ---
kubectl -n <gateway-ns> port-forward svc/burstops-gateway 8080:8080 &
curl -s localhost:8080/health; echo                      # mode: baseline
curl -s localhost:8080/calculate | python3 -m json.tool   # source: k8s, 168 / 76127

# --- F. Ingress + TLS (skip if the user chose option (i)) ---
kubectl -n <gateway-ns> get ingress -o wide
HOST=$(kubectl -n <gateway-ns> get ingress burstops -o jsonpath='{.spec.rules[0].host}')
kubectl -n <gateway-ns> get certificate,certificaterequest,order,challenge
curl -sk  "https://$HOST/health"; echo        # -k: expected while on the staging issuer
curl -sSv "https://$HOST/health" 2>&1 | grep -E 'issuer|subject|HTTP/'   # after prod switch
```

### 7g. The burst demo, and how not to fool yourself

There is no `cpu-sim` here, and you should not deploy one: in AKS the real cAdvisor
series already exist, and synthetic `container_cpu_usage_seconds_total` series
carrying `namespace="burstops"` would be averaged in alongside them, making the
observed number a fiction. Drive **real** CPU instead:

```bash
# hammer the backend's CPU-burn path through the gateway
for i in $(seq 1 200); do curl -s -o /dev/null "http://localhost:8080/calculate" & done; wait
# or, better, the endpoint dummy-backend exposes for exactly this:
kubectl -n burstops exec deploy/burstops-backend -- sh -c 'echo use /burn-cpu via the gateway'
# then watch
for i in $(seq 1 30); do printf '%02ds ' $((i*5)); curl -s localhost:8080/health; echo; sleep 5; done
```

**Distinguish a real burst from a fail-open burst.** `gateway.py` fails open to
`burst` when Prometheus polling goes stale past the 15s grace period. On a single
B2s node, saturating both backend replicas can starve the gateway's own poller, so
the mode flips to `burst` for the wrong reason and the demo looks like it worked.
Check both, every time:

```bash
curl -s localhost:8080/metrics | grep -E 'gateway_cpu_observed_percent|gateway_prometheus_poll_failures_total|gateway_routing_mode|gateway_state_transitions_total'
```

If `gateway_prometheus_poll_failures_total` is climbing, the burst came from
fail-open, not from crossing 80. Report which one you observed — that distinction is
the difference between demonstrating the feature and demonstrating a timeout.

### 7h. The Function path really is reachable from the cluster

```bash
kubectl -n <gateway-ns> logs deploy/burstops-gateway --tail=50
curl -s localhost:8080/calculate | python3 -m json.tool
# in burst: source "serverless", impl "azure-function", a real instance_id
curl -s localhost:8080/metrics | grep -E 'gateway_requests_routed_total|gateway_upstream_latency_seconds_count'
```

`impl: "azure-function"` arriving through the in-cluster gateway is Phase 6's
headline assertion: a pod on AKS signed a request that real Azure infrastructure
accepted. If it fails, check egress and DNS from inside the pod before touching
anything else.

### 7i. Grafana

Port-forward Grafana, log in, confirm the datasource uid is `burstops-prometheus`
and that all six panels of "BurstOps — Burst Routing Monitor" render data rather
than "datasource not found". Describe each panel's state.

### Pass criteria

- Every pod `Running`, nothing `Pending`, nothing in `CrashLoopBackOff` or
  `ImagePullBackOff`.
- Prometheus lists the gateway target as `up`, and all six `gateway_*` metric names
  are present and identical to the Compose set.
- §2's series-count query answered, with the dilution question resolved by an
  explicit user decision — not by you picking one.
- `/health` reports `mode: baseline` and `/calculate` returns `source: "k8s"` with
  `prime_count` 168 and `prime_sum` 76127.
- If an Ingress was chosen: it terminates TLS with a Let's Encrypt **prod**
  certificate and `/health` answers over `https://`.
- Under real load the mode flips to `burst`, `/calculate` returns
  `source: "serverless"` and `impl: "azure-function"`, and
  `gateway_prometheus_poll_failures_total` stayed flat while it happened.
- Mode returns to `baseline` after load stops, and
  `gateway_state_transitions_total` shows both directions with count ≥ 1.
- `tests/` still passes untouched: `pytest tests/ -q`.

## 8. `docs/phase6-runbook.md`

One page, in this order, with real resource names substituted rather than
placeholders: prerequisites and `az aks get-credentials`; build and push (§6a);
create the Secret from Key Vault (§3); `kubectl apply -k k8s/`; verify (the §7
commands, condensed); the demo sequence (three commands, baseline → burst → back);
rollback (`kubectl rollout undo`, and how to redeploy a previous image tag); and
teardown:

```bash
kubectl delete -k k8s/
helm uninstall ingress-nginx -n ingress-nginx
helm uninstall cert-manager  -n cert-manager
helm uninstall kps -n monitoring
az aks stop --name aks-burstops -g rg-burstops-prod    # stops node billing
```

Call out that `kubectl delete` on the ingress-nginx Service is what releases the
public IP, and that leaving the cluster running is the single largest cost in the
whole project — `az aks stop` between sessions is the habit that matters.

## 9. Stop and ask — do not decide these yourself

- **§2's metric dilution.** Present the measurement and the three options. Do not
  pick one, and above all do not edit `gateway.py`'s `PROM_QUERY` without explicit
  permission.
- **Exposing the gateway publicly** (§5). It has no inbound authentication. Get a
  decision on options (i)–(iv) before applying an Ingress.
- Changing `backend-service.yaml` from `LoadBalancer` to `ClusterIP` (§6c), or any
  other edit to the two existing manifests — including reformatting them.
- The gateway Dockerfile's `CMD` runs `gateway:app` rather than the entrypoint shim
  (§6a). Report it; the fix is inside `gateway/`.
- Anything does not fit on one B2s node. Show the `Pending` pods and the
  `describe node` allocation, then present the choices (second node, trimmed
  Prometheus, fewer backend replicas) rather than scaling the node pool yourself —
  it changes the bill.
- Adding an **HPA** to the backend. It is the natural next step and it is genuinely
  interesting here (BurstOps exists to cover HPA lag, so watching both operate
  together is the real demo), but it needs metrics-server confirmed and node
  headroom that one B2s may not have. Propose it, don't add it.
- Provisioning an Application Gateway, a second node pool, Azure Monitor managed
  Prometheus, or anything else with a recurring charge.

## 10. Report back with

1. §1's verification output: the exact env var names the shim reads, allocatable CPU
   per node, whether a `burstops` Namespace object already existed, and the Terraform
   outputs you used.
2. **§2's measurement** — the series count with pod/container labels, the value the
   gateway's query actually returns under load, and the option you are recommending
   with the user's decision recorded.
3. Every file you created, in full, plus confirmation via `git diff --stat` that
   `backend-deployment.yaml`, `backend-service.yaml`, `gateway/` and `.env` are
   untouched.
4. The image build output and the ACR tag listing.
5. The §7 acceptance output, command by command, with a pass/fail line per criterion.
6. Which ingress option (i)–(iv) the user chose, and the resulting exposure surface
   stated plainly.
7. Observed burst behaviour: time-to-flip, the CPU value at the transition, the
   value at recovery, and confirmation that poll failures stayed flat.
8. `gateway_upstream_latency_seconds` p95 for `route="serverless"` from inside the
   cluster, compared against Phase 4's numbers from your laptop — the difference is
   the network path, and it is worth knowing.
9. Everything flagged under §9, and the monthly cost delta this phase added
   (Load Balancer + public IP + any extra node).

Do not implement Upgrades A–D. Each has its own brief.










