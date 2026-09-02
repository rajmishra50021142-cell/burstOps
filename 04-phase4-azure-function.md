# PROMPT 04 — Phase 4: real Azure Function

> Paste this entire file to the coding agent as its task. It is self-contained.

## Your role

You are working on **BurstOps**, a Layer-7 gateway that compensates for
Kubernetes HPA provisioning lag. When cluster CPU crosses 80%, the gateway stops
sending overflow traffic to Kubernetes and deflects it to a serverless upstream,
returning to Kubernetes when CPU drops below 60%.

Until now that serverless upstream has been `dummy-serverless/`, a local FastAPI
service. This task replaces it with a **real Azure Function**, keeping the wire
contract byte-identical so the gateway does not change at all.

`dummy-serverless/` stays in the repo. It is the local-development stand-in and
the fixture the whole Compose stack still depends on. Do not delete it.

## Scope

```
azure-function/
├── function_app.py             # V2 Python programming model
├── hmac_util.py                # lifted verbatim from dummy-serverless/
├── requirements.txt
├── host.json
├── local.settings.json.example # committed template
├── .funcignore
├── .gitignore                  # must ignore local.settings.json
└── README.md                   # deploy + rollback steps
tests/
└── test_hmac_contract.py       # extend the existing file (see §6)
```

Do not modify `gateway/gateway.py`, `gateway/gateway_entrypoint.py`, `.env`,
`docker-compose.yml`, `dummy-serverless/`, `k8s/`, or
`tests/test_hysteresis.py`. §8 lists what to flag instead.

## 1. Verify before you write anything

```bash
sed -n '1,240p' gateway/gateway.py
grep -n -A 25 'def sign_request' gateway/gateway.py
cat dummy-serverless/hmac_util.py
cat dummy-serverless/app.py
cat dummy-backend/app.py | grep -n -A 20 'calculate'
grep -n 'FUNCTION_UPSTREAM\|FUNCTION_KEY\|GATEWAY_HMAC_SECRET' .env docker-compose.yml gateway/gateway_entrypoint.py

# toolchain + what the platform actually supports right now
func --version                    # Azure Functions Core Tools v4 required
az --version
az functionapp list-runtimes --os linux --query "[?runtime=='python']" -o table
```

Report: the exact `sign_request()` source, the exact `hmac_util.py` source you are
about to lift, the backend's `/calculate` JSON keys, and the Python versions the
platform currently offers for Linux Functions.

**On the Python version:** target **3.13**. Microsoft has published guidance that
Function Apps on Python 3.12 should move to 3.13 by 1 October 2026, and both were
GA on Functions runtime v4. But availability differs by hosting plan — Flex
Consumption has historically lagged on new Python versions. Take the newest
version the `az functionapp list-runtimes` output above actually offers for the
plan you will deploy to, and state which you picked and why. Do not hardcode a
version this prompt asserts without confirming it.

## 2. The wire contract — this cannot drift

The gateway signs every forwarded request like this:

```python
timestamp = str(int(time.time()))
signature = hmac.new(
    GATEWAY_HMAC_SECRET.encode("utf-8"),
    f"{timestamp}:".encode("utf-8") + body,
    hashlib.sha256,
).hexdigest()
```

and sends three headers: `x-functions-key`, `x-gateway-timestamp`,
`x-gateway-signature`. The Function must verify exactly this. Header names,
the `f"{timestamp}:"` prefix, UTF-8 encoding of the secret, SHA-256, hex digest —
all fixed.

These golden vectors are correct as printed. Your `hmac_util.compute_signature`
must reproduce them:

```
secret="local-dev-secret-change-in-prod", ts="1700000000", body=b""
  -> 7545c853772dd927b78111771008f1ace824d14fd36c02e7c00b301ac3ab933b
secret="local-dev-secret-change-in-prod", ts="1700000000", body=b'{"n":100}'
  -> 263942c72316a870e757782819c315e543e1653dd9481beae4d6b53abb525d75
secret="test-secret", ts="1700000000", body=b""
  -> 0f5d899b28266feacd0515cc219efef93968c602c49ecf488c15da01dba0b4a3
secret="test-secret", ts="1700000000", body=b'{"n":100}'
  -> 0bd99a3457b14815fed94d47656212f1a92580d93f8806cf86e67f87642a022b
```

**GET requests carry an empty body**, and the Locust profile sends 95% GETs, so
the empty-body case is the common path, not an edge case. Handle `body == b""`.

## 3. `hmac_util.py` — copy, don't rewrite

Copy `dummy-serverless/hmac_util.py` into `azure-function/` **byte for byte**.
Add only a header comment naming `dummy-serverless/hmac_util.py` as the source of
truth and warning that the two copies must stay identical.

Duplicating rather than sharing is deliberate: Azure Functions packages a single
deployment directory, and reaching outside it for a sibling module means fragile
`sys.path` manipulation or a build step. A 60-line duplicated file plus a test
that proves the copies agree (§6) is the cheaper trade. Say so in the README so
the next person does not "fix" it.

Do not import `fastapi`, `httpx`, or anything else third-party into this module.
Stdlib only.

## 4. `function_app.py` — V2 programming model

Single file, decorator-based registration, no `function.json` files anywhere (that
is the V1 model and mixing them fails at load time).

```python
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="calculate", methods=[func.HttpMethod.GET, func.HttpMethod.POST])
def calculate(req: func.HttpRequest) -> func.HttpResponse:
    ...
```

Design points, each of which matters:

- **Route must be `calculate`.** The gateway's `FUNCTION_UPSTREAM` will be
  `https://<app>.azurewebsites.net/api/calculate`. The default route prefix `api`
  comes from `host.json`; leave it at the default and let the URL carry it.
- **`AuthLevel.FUNCTION` means the platform validates `x-functions-key` for you**
  and returns **401** on a bad or missing key before your code runs. Keep your own
  key check anyway, because the local `func start` host does not enforce keys —
  without it, local testing would pass requests the cloud would reject. Note the
  status-code difference in your report: `dummy-serverless` returns 403 for a bad
  key, Azure returns 401. Both are acceptable; the contract is "rejected".
- **Read the body as raw bytes** with `req.get_body()`. Never
  `req.get_json()`-then-reserialize before signing — the bytes would change and
  every signature would fail.
- **Verify in the same order** `hmac_util.verify_request` already implements: key,
  then timestamp presence/parse, then skew, then signature. Return the same
  status codes it raises.
- **No artificial latency.** `dummy-serverless` injects 50–150 ms to imitate a
  cold-ish Function. A real Function has real cold starts; adding fake delay on
  top would corrupt the `gateway_upstream_latency_seconds` histogram that the
  Grafana "Upstream Latency p95" panel reads. Delete that logic during the port.
- **Do the real work.** Sieve of Eratosthenes up to 1000, same as
  `dummy-backend/app.py`. It must produce **168 primes summing to 76127**. A stub
  echo would make the latency comparison meaningless.
- **Log, don't leak.** Use the `logging` module (output flows to Application
  Insights). Never log the secret, the function key, or a full signature — at most
  the first 8 hex characters of a rejected one, plus the reason.

Response payload mirrors the dummy's, with the implementation distinguishable:

```json
{
  "source": "serverless",
  "impl": "azure-function",
  "instance_id": "<os.environ.get('WEBSITE_INSTANCE_ID','local')[:8]>",
  "prime_count": 168,
  "prime_sum": 76127,
  "cold_start": true
}
```

`source` stays the literal `"serverless"` — the gateway's `route` label, the
Grafana panels, and later phases all key off that word. `cold_start` from a
module-level flag flipped on first invocation, and `instance_id` truncated from
`WEBSITE_INSTANCE_ID`, together make Azure's scale-out visible in the response,
which is the whole point of the burst path.

Match the dummy backend's actual key names from §1 if they differ from
`prime_count` / `prime_sum`.

## 5. Supporting files

`requirements.txt` — keep it minimal; every extra wheel lengthens cold start:

```
azure-functions
```

Pin it to a concrete version once you have resolved one (`pip index versions
azure-functions`) and record which. Do not add `fastapi`, `httpx`, or
`prometheus-client` — none is used.

`host.json`:

```json
{
  "version": "2.0",
  "logging": {
    "applicationInsights": {
      "samplingSettings": { "isEnabled": true, "excludedTypes": "Request" }
    }
  },
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  }
}
```

App Insights sampling stays enabled deliberately — ingestion is billed, and this
is a cost-minimized subscription. `excludedTypes: "Request"` keeps every HTTP
request visible while sampling the noisier trace types.

`local.settings.json.example` — committed template, never the real file:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "GATEWAY_HMAC_SECRET": "local-dev-secret-change-in-prod",
    "FUNCTION_KEY": "local-dev-function-key",
    "MAX_CLOCK_SKEW_SECONDS": "300"
  }
}
```

`.gitignore` inside `azure-function/` must contain `local.settings.json`,
`.python_packages/`, `__pycache__/`, `.venv/`. A committed `local.settings.json`
is how HMAC secrets end up in git history — do not let it happen.

`.funcignore` should exclude `local.settings.json`, `.venv/`, `tests/`,
`__pycache__/`, `.git*` from the deployment package.

Read the app settings with `os.environ` at module scope with sane fallbacks, the
same way `dummy-serverless/app.py` does: `GATEWAY_HMAC_SECRET`, `FUNCTION_KEY`,
`MAX_CLOCK_SKEW_SECONDS` (default 300). The env var **names must match** the ones
the gateway side already uses — Phase 5's Terraform will inject them as app
settings under exactly these names.

## 6. Extend `tests/test_hmac_contract.py`

Add to the existing file (created alongside `dummy-serverless/`); do not create a
second one, and do not touch `tests/test_hysteresis.py`.

New cases:

1. Import both `dummy-serverless/hmac_util.py` and `azure-function/hmac_util.py`
   under distinct module names (`importlib.util.spec_from_file_location`) and
   assert `compute_signature` returns identical output for all four golden vectors
   **and** for a handful of randomized `(secret, timestamp, body)` triples. This is
   the test that catches the two copies drifting apart.
2. Assert the two files are textually identical apart from leading comment lines —
   or, if you prefer not to be that strict, assert their `verify_request`
   signatures match via `inspect.signature`.
3. Re-run every existing case to confirm nothing regressed.

`pytest tests/ -q` must be fully green.

## 7. Acceptance

### 7a. Local, with the Functions host — do this first

```bash
cd azure-function
cp local.settings.json.example local.settings.json
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
func start                     # serves http://localhost:7071/api/calculate
```

In another shell, reuse the same signing helper the local stack uses:

```bash
sign() { python3 - "$1" "$2" <<'PY'
import hmac, hashlib, sys
ts, body = sys.argv[1], sys.argv[2].encode()
print(hmac.new(b"local-dev-secret-change-in-prod", f"{ts}:".encode()+body, hashlib.sha256).hexdigest())
PY
}
code() { curl -s -o /tmp/b -w '%{http_code}' "$@"; echo " <- $(cat /tmp/b)"; }
U=http://localhost:7071/api/calculate
TS=$(date +%s)

code "$U" -H "x-functions-key: local-dev-function-key" \
  -H "x-gateway-timestamp: $TS" -H "x-gateway-signature: $(sign "$TS" '')"          # 200

SIG=$(sign "$TS" '{"n":100}')
code -X POST "$U" -H 'content-type: application/json' \
  -H "x-functions-key: local-dev-function-key" -H "x-gateway-timestamp: $TS" \
  -H "x-gateway-signature: $SIG" -d '{"n":100}'                                      # 200

code -X POST "$U" -H 'content-type: application/json' \
  -H "x-functions-key: local-dev-function-key" -H "x-gateway-timestamp: $TS" \
  -H "x-gateway-signature: $SIG" -d '{"n":999}'                                      # 401 tampered

OLD=$((TS-600))
code "$U" -H "x-functions-key: local-dev-function-key" \
  -H "x-gateway-timestamp: $OLD" -H "x-gateway-signature: $(sign "$OLD" '')"        # 401 stale

code "$U" -H "x-functions-key: wrong" -H "x-gateway-timestamp: $TS" \
  -H "x-gateway-signature: $(sign "$TS" '')"                                         # 401/403 bad key

code "$U"                                                                            # 401/403 no headers
```

Expected: 200, 200, 401, 401, 401-or-403, 401-or-403. The 200 body must contain
`prime_count` 168 and `prime_sum` 76127.

### 7b. Against the deployed Function

Requires Phase 5's Terraform to have created the Function App. If it has not yet
run, stop here, report 7a's results, and say that 7b is pending Phase 5.

```bash
FUNC_URL="https://<app>.azurewebsites.net/api/calculate"
KEY=$(az functionapp keys list -g <rg> -n <app> --query 'functionKeys.default' -o tsv)
SECRET="<the value Terraform put in Key Vault>"
```

Repeat the same six cases against `$FUNC_URL` with the real key and secret, using
a signing helper parameterised on `$SECRET` rather than the hardcoded dev value.
Then confirm the end-to-end path:

```bash
# Point the LOCAL gateway at the REAL function without editing .env.
# Create .env.azure as an overlay (new file, safe) and run compose with it.
cat > .env.azure <<EOF
FUNCTION_UPSTREAM=$FUNC_URL
FUNCTION_KEY=$KEY
GATEWAY_HMAC_SECRET=$SECRET
EOF
echo '.env.azure' >> .gitignore

docker compose --env-file .env --env-file .env.azure up -d gateway
curl -X POST http://localhost:8002/ramp-up
sleep 35
curl -s http://localhost:8080/health; echo                  # mode: burst
curl -s http://localhost:8080/calculate | python3 -m json.tool
# expect: source "serverless", impl "azure-function", a real instance_id
curl -s http://localhost:8080/metrics | grep -E 'gateway_requests_routed_total|gateway_upstream_latency_seconds_count'
curl -X POST http://localhost:8002/ramp-down
```

The second-to-last command is the one that matters: `impl: "azure-function"`
arriving through the gateway means a request signed by the untouched
`gateway.py` was accepted by real Azure infrastructure. That is Phase 4's
acceptance criterion.

Note the observed p95 of `gateway_upstream_latency_seconds{route="serverless"}`
against the real Function and compare it to the dummy's 50–150 ms. Cold starts
will make the first few requests much slower. Report both numbers — that gap is
the honest story about what deflecting to serverless costs in latency.

## 8. Stop and ask — do not decide these yourself

- **Do not edit `.env`.** Use the `.env.azure` overlay above. `.env`'s
  `FUNCTION_UPSTREAM` must keep pointing at `http://dummy-serverless:8001/calculate`
  so the local stack still works offline.
- **Do not delete `dummy-serverless/`.** `docker-compose.yml` and the whole local
  workflow depend on it.
- `gateway.py`'s real `sign_request()` differs from §2 in any way — report the
  actual source and wait.
- The Python version you want is not offered for the plan Phase 5 provisions, or
  `az functionapp list-runtimes` disagrees with §1's guidance.
- You are tempted to change `AuthLevel`, the route name, or the `api` prefix.
  Any of those changes `FUNCTION_UPSTREAM`, which changes `.env`, which is off
  limits without asking.
- Deployment requires resources that do not exist yet — that is Phase 5's job,
  not something to improvise with `az functionapp create`.

## 9. Report back with

1. The `sign_request()` source and confirmation the ported `hmac_util.py` is
   byte-identical to `dummy-serverless/`'s.
2. Every file you created, in full.
3. The Python version chosen and the `az functionapp list-runtimes` evidence.
4. `pytest tests/ -q` output.
5. §7a's six status codes with a pass/fail line each, plus the 200 body.
6. §7b's results, or an explicit note that it is blocked on Phase 5.
7. Cold-start and warm latency numbers for the real Function vs the dummy.
8. Confirmation that `.env`, `gateway/`, and `dummy-serverless/` are unmodified
   (`git status --short` and `git diff --stat`).

Do not write Terraform, Kubernetes manifests, or any gateway upgrade. Those are
separate tasks with their own briefs.





