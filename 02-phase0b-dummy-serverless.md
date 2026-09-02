# PROMPT 02 — Phase 0b: build `dummy-serverless/`

> Paste this entire file to the coding agent as its task. It is self-contained.

## Your role

You are working on **BurstOps**, a local Docker Compose prototype of a Layer-7
gateway that compensates for Kubernetes HPA provisioning lag. When cluster CPU
crosses a threshold the gateway stops sending overflow traffic to Kubernetes and
deflects it to a serverless upstream instead, then returns to Kubernetes when CPU
recovers.

`dummy-serverless/` is that serverless upstream, standing in for an Azure
Function so the whole system runs on a laptop with no Azure credentials. **The
directory does not exist.** `docker-compose.yml` declares a service built from
`./dummy-serverless`, `.env` points `FUNCTION_UPSTREAM` at
`http://dummy-serverless:8001/calculate`, and the README's architecture diagram
assumes it. Nothing has ever been there.

Build it. This is also the file Phase 4 later ports its HMAC validation out of
when the real Azure Function is written, so write the crypto to be liftable.

## Scope — one new directory

```
dummy-serverless/
├── hmac_util.py        # pure stdlib, zero third-party imports (see §3)
├── app.py              # FastAPI service on port 8001
├── requirements.txt
├── Dockerfile
└── .dockerignore
tests/
└── test_hmac_contract.py   # new file, dependency-free pytest
```

Do not modify `gateway/gateway.py`, `gateway/gateway_entrypoint.py`,
`docker-compose.yml`, `.env`, `prometheus/prometheus.yml`,
`tests/test_hysteresis.py`, or anything under `dummy-backend/`, `k8s/`, or
`grafana/`. If you think one of them needs changing, stop and ask.

## 1. Verify before you write anything

The gateway's signing function is the contract. Read it, do not trust this
prompt's paraphrase of it:

```bash
ls -la dummy-serverless/ 2>&1        # expect: does not exist
sed -n '1,240p' gateway/gateway.py   # read the whole thing
grep -n -A 25 'def sign_request' gateway/gateway.py
grep -n -E 'FUNCTION_UPSTREAM|FUNCTION_KEY|GATEWAY_HMAC_SECRET|x-functions-key|x-gateway' gateway/gateway.py gateway/gateway_entrypoint.py .env docker-compose.yml
grep -n -B3 -A20 'calculate' gateway/gateway.py
cat dummy-backend/app.py
docker compose config | sed -n '/dummy-serverless/,/^  [a-z]/p'
```

Extract and report these five facts from what you read:

1. **Exact signing input.** The documented scheme is
   `HMAC_SHA256(GATEWAY_HMAC_SECRET, f"{timestamp}:".encode() + body).hexdigest()`
   with `timestamp = str(int(time.time()))`. Confirm from the source: is the
   secret `.encode()`d as UTF-8? Is `body` the raw bytes of the outgoing request
   body? Is the digest hex (not base64)? Any deviation, report it and follow the
   source, not this prompt.
2. **Exact header names.** Expected: `x-functions-key`, `x-gateway-timestamp`,
   `x-gateway-signature`. HTTP headers are case-insensitive, so read them
   case-insensitively on your side regardless.
3. **Which HTTP methods `/calculate` accepts on the gateway.** It should be GET
   and POST. **This matters more than it looks:** the Locust load generator sends
   95% `GET /calculate`, so in burst mode the majority of what reaches you will
   be GETs with an empty body. Your service must accept GET as well as POST, and
   your signature check must handle `body == b""`.
4. **Whether the gateway forwards the query string** to the upstream, and whether
   it forwards any inbound headers. The signature covers timestamp + body only,
   so query params are unsigned — note that as a known limitation, don't try to
   fix it here.
5. **The exact JSON shape of `dummy-backend/app.py`'s `/calculate` response** —
   key names, and where `source: "k8s"` sits. Yours will mirror it with
   `source: "serverless"`.

## 2. Behaviour specification

Service listens on **8001** (baked into `FUNCTION_UPSTREAM`; do not pick another
port). Endpoints:

| Route | Methods | Auth | Behaviour |
|---|---|---|---|
| `/calculate` | GET, POST | full HMAC + key check | validate, inject latency, do real work, return JSON |
| `/health` | GET | none | `{"status":"ok"}` — used by compose/depends_on, must never require signing |

Rejection semantics, in this order:

| Condition | Status | Body |
|---|---|---|
| `x-functions-key` missing or != `FUNCTION_KEY` | **403** | `{"detail":"invalid function key"}` |
| `x-gateway-timestamp` missing / not an integer | **401** | `{"detail":"invalid timestamp"}` |
| `abs(now - timestamp) > MAX_CLOCK_SKEW_SECONDS` | **401** | `{"detail":"stale timestamp"}` |
| `x-gateway-signature` missing or mismatched | **401** | `{"detail":"invalid signature"}` |
| all good | 200 | payload from §5 |

Rules that matter:

- Compare signatures with `hmac.compare_digest`, never `==`. Timing-safe
  comparison is the entire point of having a signature.
- **Never log the secret, the function key, or a full signature.** Log at most
  the first 8 hex characters of a rejected signature plus the reason. Reject
  bodies must not echo the expected value.
- Read the raw body with `await request.body()` and sign **those exact bytes**.
  Do not parse JSON and re-serialize it before signing — key ordering and
  whitespace would change the bytes and every signature would fail.
- Check the key before the signature so a wrong-key caller never learns anything
  about signature validity.

## 3. `dummy-serverless/hmac_util.py` — keep the crypto separate

Put the verification logic in its own module with **zero third-party imports**
(`hmac`, `hashlib`, `time` only). Two reasons: Phase 4 lifts this file verbatim
into the Azure Function, and a stdlib-only module can be unit-tested without
FastAPI installed — which is how `tests/test_hysteresis.py` already works.

Required public surface, exactly these names:

```python
DEFAULT_MAX_CLOCK_SKEW_SECONDS = 300

def compute_signature(secret: str, timestamp: str, body: bytes) -> str:
    """Reference implementation, mirrors gateway.py's sign_request()."""
    return hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}:".encode("utf-8") + body,
        hashlib.sha256,
    ).hexdigest()


class SignatureError(Exception):
    """Carries .status_code (401/403) and .reason (short, safe to log)."""


def verify_request(
    *,
    secret: str,
    expected_function_key: str,
    provided_function_key: str | None,
    timestamp: str | None,
    signature: str | None,
    body: bytes,
    max_skew_seconds: int = DEFAULT_MAX_CLOCK_SKEW_SECONDS,
    now: float | None = None,      # injectable for deterministic tests
) -> None:
    """Raise SignatureError on any failure; return None when the request is valid."""
```

`now` being injectable is not optional — the stale-timestamp test needs to pin
the clock rather than sleep.

Keep the ordering of checks identical to §2's table, use `hmac.compare_digest`
for both the key and the signature comparison, and make `verify_request` raise
rather than return a bool so a caller cannot accidentally ignore the result.

## 4. `dummy-serverless/app.py`

FastAPI app named `app`. Config from environment, with the defaults below so the
service also runs standalone:

| Env var | Default | Notes |
|---|---|---|
| `GATEWAY_HMAC_SECRET` | `local-dev-secret-change-in-prod` | must match `.env` |
| `FUNCTION_KEY` | `local-dev-function-key` | must match `.env` |
| `MAX_CLOCK_SKEW_SECONDS` | `300` | replay window |
| `MIN_LATENCY_MS` | `50` | artificial cold-ish Function latency |
| `MAX_LATENCY_MS` | `150` | |
| `PRIME_LIMIT` | `1000` | mirrors the backend's sieve bound |
| `PORT` | `8001` | |

Handler outline:

```python
@app.api_route("/calculate", methods=["GET", "POST"])
async def calculate(request: Request):
    body = await request.body()            # b"" for GET — that is expected
    h = request.headers                    # case-insensitive mapping
    try:
        verify_request(
            secret=SECRET,
            expected_function_key=FUNCTION_KEY,
            provided_function_key=h.get("x-functions-key"),
            timestamp=h.get("x-gateway-timestamp"),
            signature=h.get("x-gateway-signature"),
            body=body,
            max_skew_seconds=MAX_SKEW,
        )
    except SignatureError as exc:
        logger.warning("rejected request: %s", exc.reason)   # no secrets, no full sig
        raise HTTPException(status_code=exc.status_code, detail=exc.reason)

    injected_ms = random.uniform(MIN_LATENCY_MS, MAX_LATENCY_MS)
    await asyncio.sleep(injected_ms / 1000.0)                # async sleep, not time.sleep
    ...
```

`await asyncio.sleep(...)` rather than `time.sleep(...)` matters: a blocking sleep
in an async handler serializes every concurrent request and the service will look
broken under Locust load.

Then do the same real work the backend does — a sieve of Eratosthenes up to
`PRIME_LIMIT`, so the serverless path is comparable rather than a stub echo — and
return a payload that mirrors `dummy-backend/app.py`'s keys with the source
swapped:

```json
{
  "source": "serverless",
  "impl": "dummy-serverless",
  "hostname": "<socket.gethostname()>",
  "prime_count": 168,
  "prime_sum": 76127,
  "injected_latency_ms": 92.4,
  "cold_start": false
}
```

Match `dummy-backend/app.py`'s actual key names from §1.5 — if it calls them
`count` and `sum`, use those. `source` must be the string `"serverless"`; the
gateway's own `route` label uses the same word, and later phases key dashboards
and traces off it. `impl` is yours to distinguish this dummy from the real Azure
Function that replaces it in Phase 4.

`cold_start`: set a module-level flag, return `true` on the first request served
by the process and `false` after. Cheap, and it makes the "this is simulating a
Function" story visible in the response.

Also add `GET /health` returning `{"status": "ok"}` with **no** signature check.

Do **not** add a `/metrics` endpoint. `prometheus/prometheus.yml` has four scrape
jobs and this service is not one of them; adding one would need a change to
that file, which is out of scope here.

## 5. `requirements.txt`, `Dockerfile`, `.dockerignore`

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
```

Same pins as `gateway/requirements.txt`. No `httpx`, no `prometheus-client`.

Dockerfile mirrors `gateway/Dockerfile` — read it first and match its
conventions:

```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY hmac_util.py app.py ./
EXPOSE 8001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
```

`.dockerignore`: `__pycache__/`, `*.pyc`, `.venv/`, `.pytest_cache/`, `.DS_Store`.

## 6. `tests/test_hmac_contract.py`

Dependency-free pytest, matching the style of the existing
`tests/test_hysteresis.py` (which imports from source directly and stubs
third-party modules rather than requiring the runtime). Import `hmac_util` by
inserting `dummy-serverless/` onto `sys.path` — do **not** import `app.py`, which
would pull in FastAPI.

These four golden vectors are correct as printed. Assert against them literally
so any future refactor that changes the signing bytes fails loudly:

```python
VECTORS = [
    # (secret, timestamp, body, expected_hex)
    ("local-dev-secret-change-in-prod", "1700000000", b"",
     "7545c853772dd927b78111771008f1ace824d14fd36c02e7c00b301ac3ab933b"),
    ("local-dev-secret-change-in-prod", "1700000000", b'{"n":100}',
     "263942c72316a870e757782819c315e543e1653dd9481beae4d6b53abb525d75"),
    ("test-secret", "1700000000", b"",
     "0f5d899b28266feacd0515cc219efef93968c602c49ecf488c15da01dba0b4a3"),
    ("test-secret", "1700000000", b'{"n":100}',
     "0bd99a3457b14815fed94d47656212f1a92580d93f8806cf86e67f87642a022b"),
]
```

Required test cases:

1. `compute_signature` reproduces all four vectors exactly.
2. A valid request passes `verify_request` (pin `now` to the timestamp).
3. Wrong function key → `SignatureError` with `status_code == 403`.
4. Missing function key → 403.
5. Missing / non-integer timestamp → 401.
6. Timestamp `now - 301` and `now + 301` → 401 (both directions of skew).
7. Timestamp `now - 299` → passes (boundary is inclusive-ish; assert the
   behaviour you implemented and make the boundary explicit either way).
8. Signature computed over a *different* body → 401. This is the tamper case.
9. Empty body GET-style request with a correct signature → passes.
10. A signature that is the right length but all zeros → 401, and the failure
    path does not raise anything other than `SignatureError`.

Run `pytest tests/ -q` and confirm **both** files pass — the pre-existing
hysteresis suite must stay green and untouched.

## 7. Acceptance — run all of it, paste all output

```bash
pytest tests/ -q                                  # both suites green

docker compose build dummy-serverless
docker compose up -d dummy-serverless
docker compose ps dummy-serverless

# health is unauthenticated
curl -fsS http://localhost:8001/health; echo

# --- helper: sign a request the way gateway.py does ---
sign() {  # $1=timestamp  $2=body
  python3 - "$1" "$2" <<'PY'
import hmac, hashlib, sys
ts, body = sys.argv[1], sys.argv[2].encode()
print(hmac.new(b"local-dev-secret-change-in-prod", f"{ts}:".encode()+body, hashlib.sha256).hexdigest())
PY
}
code() { curl -s -o /tmp/body -w '%{http_code}' "$@"; echo " <- $(cat /tmp/body)"; }

TS=$(date +%s)

# 1. valid POST with body  -> 200
SIG=$(sign "$TS" '{"n":100}')
code -X POST http://localhost:8001/calculate -H "content-type: application/json" \
  -H "x-functions-key: local-dev-function-key" -H "x-gateway-timestamp: $TS" \
  -H "x-gateway-signature: $SIG" -d '{"n":100}'

# 2. valid GET, empty body -> 200
SIG=$(sign "$TS" '')
code http://localhost:8001/calculate -H "x-functions-key: local-dev-function-key" \
  -H "x-gateway-timestamp: $TS" -H "x-gateway-signature: $SIG"

# 3. stale timestamp (10 min old, sig valid for it) -> 401
OLD=$((TS-600)); SIG=$(sign "$OLD" '')
code http://localhost:8001/calculate -H "x-functions-key: local-dev-function-key" \
  -H "x-gateway-timestamp: $OLD" -H "x-gateway-signature: $SIG"

# 4. tampered body, signature from a different body -> 401
SIG=$(sign "$TS" '{"n":100}')
code -X POST http://localhost:8001/calculate -H "content-type: application/json" \
  -H "x-functions-key: local-dev-function-key" -H "x-gateway-timestamp: $TS" \
  -H "x-gateway-signature: $SIG" -d '{"n":999}'

# 5. wrong function key -> 403
SIG=$(sign "$TS" '')
code http://localhost:8001/calculate -H "x-functions-key: wrong" \
  -H "x-gateway-timestamp: $TS" -H "x-gateway-signature: $SIG"

# 6. no auth headers at all -> 403
code http://localhost:8001/calculate

# 7. latency really is injected: 20 sequential calls, all between 50-150ms
SIG=$(sign "$TS" '')
for i in $(seq 1 20); do curl -s -o /dev/null -w '%{time_total}\n' \
  http://localhost:8001/calculate -H "x-functions-key: local-dev-function-key" \
  -H "x-gateway-timestamp: $TS" -H "x-gateway-signature: $SIG"; done

# 8. no secrets in the logs
docker compose logs dummy-serverless | grep -iE 'secret|local-dev' || echo "clean: no secret material in logs"
```

Pass criteria: 200, 200, 401, 401, 403, 403 for cases 1–6 in that order; case 7's
20 timings all fall in roughly 0.05–0.16s and are not identical to each other
(proving the latency is randomised, not a constant); case 8 finds no secret
material in the logs; `pytest tests/ -q` fully green.

**End-to-end through the gateway is deliberately not tested here.** Reaching the
serverless path requires the gateway to be in burst mode, which requires
`cpu-sim/` — the next task. Verify the direct-to-service behaviour above and stop.

If you want one extra signal without cpu-sim, temporarily start the gateway with
`FAIL_OPEN_TO_BURST` behaviour triggered by pointing `PROMETHEUS_URL` at a dead
address, wait past the 15s stale grace period, and confirm the gateway then
forwards `/calculate` to you successfully. Do this with an env override on the
command line only (`docker compose run --rm -e PROMETHEUS_URL=http://127.0.0.1:1/api/v1/query gateway`);
**do not edit `.env` or `docker-compose.yml`** to achieve it.

## 8. Stop and ask — do not decide these yourself

- `gateway.py`'s actual `sign_request()` disagrees with §1's description in any
  way. Report the real code and wait; guessing here silently breaks every request
  in burst mode.
- The gateway's `/calculate` does *not* accept GET, or forwards something you did
  not expect (extra headers, rewritten body, different path).
- You want to add `dummy-serverless` to `prometheus/prometheus.yml`, change its
  port away from 8001, or touch `.env`.
- `dummy-backend/app.py`'s response keys make "mirror the payload" ambiguous.
- The `.env` `GATEWAY_HMAC_SECRET` and `FUNCTION_KEY` values differ from the
  defaults in §4's table. Use `.env`'s values via the environment; never hardcode
  a different secret into `app.py`.

## 9. Report back with

1. The exact `sign_request()` source you read, and confirmation that
   `compute_signature` is byte-for-byte equivalent.
2. All five files, in full.
3. `pytest tests/ -q` output.
4. Every acceptance command's output with a pass/fail line per case, including
   the 20 latency samples.
5. Confirmation that `tests/test_hysteresis.py` was not modified
   (`git diff --stat` is fine).
6. A one-paragraph note for whoever does Phase 4, listing exactly what they need
   to lift out of `hmac_util.py` and what must not change.

Do not build `cpu-sim/`, the Azure Function, Terraform, or any gateway change.
Those are separate tasks with their own briefs.






