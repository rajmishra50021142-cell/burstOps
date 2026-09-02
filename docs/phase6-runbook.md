# Phase 6 Runbook — local cluster + real Azure Function

The Kubernetes-shaped tier is the local Docker Compose stack; the serverless
burst target is a real Azure Function (Flex Consumption, centralindia).
Full reasoning: `docs/architecture-decision.md`.

## Prerequisites

```bash
az login                                   # the student subscription
cd terraform && terraform apply            # function + storage + telemetry (idempotent)
terraform output function_hostname        # the live burst URL
```

## Secrets — never typed, never committed

```bash
HMAC=$(python3 -c 'import json;print([i["instances"][0]["attributes"]["result"] for r in json.load(open("terraform.tfstate"))["resources"] if r["type"]=="random_password"][0])')
FKEY=$(az functionapp keys list -g rg-burstops-prod -n func-burstops-cvkzqc --query 'functionKeys.default' -o tsv)
```

## Bring the stack up (offline mode — dummy-serverless)

```bash
docker compose up -d --build
curl localhost:8080/health          # {"mode":"baseline",...}
```

## Switch the gateway to the REAL Azure Function

`.env.azure` overlay (never edit `.env`; keep the offline stack working):

```bash
docker compose --env-file .env --env-file .env.azure up -d --force-recreate gateway
```

## The demo — three commands, baseline → burst → back

```bash
curl -X POST 'localhost:8002/set?pct=95'   # 1. saturate "the cluster"
sleep 35 && curl localhost:8080/calculate # 2. impl: "azure-function" (real Azure)
curl -X POST 'localhost:8002/set?pct=20'   # 3. recover to baseline/k8s
```

Watch `http://localhost:3000` (admin/burstops) — Routing Mode flips 0→1,
Requests Routed shows `serverless`, State Transitions counts both ways.

## Verify against real Azure directly

```bash
TS=$(date +%s)
SIG=$(python3 -c "import hmac,hashlib;s='$HMAC';print(hmac.new(s.encode(),('$TS:').encode(),hashlib.sha256).hexdigest())")
curl -s https://func-burstops-cvkzqc.azurewebsites.net/api/calculate \
  -H "x-functions-key: $FKEY" -H "x-gateway-timestamp: $TS" -H "x-gateway-signature: $SIG"
# expect: {"source":"serverless","impl":"azure-function",...,"prime_count":168,"prime_sum":76127}
```

## Teardown / steady state

```bash
docker compose down                       # local stack
terraform destroy                         # everything cloud-side (leaves ~$0.05/mo nothing)
```

Keeping the function live costs ~$0.05/mo (storage) and keeps the project
demoable indefinitely. `az functionapp stop` is unnecessary — Consumption
bills $0 at zero invocations.
