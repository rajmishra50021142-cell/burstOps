# BurstOps Azure Function (Phase 4)

Replaces `dummy-serverless/` for real Azure deployments. Wire contract is
byte-identical: gateway.py's `sign_request()` signs every forwarded request
and this Function verifies it with `hmac_util.py` — a verbatim copy of
`dummy-serverless/hmac_util.py`. The two copies MUST stay identical;
`tests/test_hmac_contract.py` enforces it against the golden vectors.

**Duplicating rather than sharing `hmac_util.py` is deliberate**: Azure
Functions packages a single deployment directory. A 60-line duplicated file
plus a test proving the copies agree is cheaper than sys.path hacks.

## Deploy

```bash
cd azure-function
cp local.settings.json.example local.settings.json   # local only
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
func start                                            # http://localhost:7071/api/calculate

# Azure (requires Phase 5's Terraform to have run):
func azure functionapp publish <func-app-name>
```

## Rollback

```bash
# redeploy the previous known-good package (kept by CI) or:
func azure functionapp publish <func-app-name>   # from the previous git tag
```

## Status codes

- Platform (`AuthLevel.FUNCTION`) rejects a bad/missing `x-functions-key`
  with **401** before this code runs. Our own key check returns **403**
  locally (same as dummy-serverless). Both mean "rejected".
- Stale timestamp or bad signature → **401** `{"detail": ...}`.

## Secrets

`GATEWAY_HMAC_SECRET`, `FUNCTION_KEY`, `MAX_CLOCK_SKEW_SECONDS` are read
from app settings (env). Phase 5 injects the HMAC secret via Key Vault
reference — never hardcoded, never committed. `local.settings.json` is
gitignored for exactly this reason.
