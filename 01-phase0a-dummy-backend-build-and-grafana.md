# PROMPT 01 — Phase 0a: make `dummy-backend` buildable and fix the Grafana datasource

> Paste this entire file to the coding agent as its task. It is self-contained.

## Your role

You are picking up **BurstOps**, a local Docker Compose prototype of a Layer-7
traffic gateway that compensates for Kubernetes HPA provisioning lag. The
gateway watches cluster CPU via Prometheus and, above a threshold, deflects
overflow traffic to a serverless upstream instead of letting the existing pods
melt. It is a shock absorber that buys HPA time, not an HPA replacement.

`docker compose up --build` **does not work today**. This task closes the two
smallest of the four gaps blocking it. Two later tasks close the others; do not
attempt them here.

## Scope — exactly four files, nothing else

Create these and change nothing else:

1. `dummy-backend/requirements.txt`
2. `dummy-backend/Dockerfile`
3. `grafana/provisioning/datasources/prometheus.yml`
4. `.dockerignore` inside `dummy-backend/` (optional but preferred, see §4)

**Do not** modify `dummy-backend/app.py`, `dummy-backend/nginx.conf`,
`docker-compose.yml`, `prometheus/prometheus.yml`,
`grafana/provisioning/dashboards/burstops.json`, `.env`, or anything under
`gateway/`, `k8s/`, or `tests/`. If you believe one of those needs to change,
stop and say so instead of changing it — see §6.

## 1. Verify before you write anything

The repo's `README.md` lists files that do not exist, and a prior handoff pass
missed two real gaps by reasoning from `docker-compose.yml` instead of listing
directories. So confirm reality first. Run these and paste the output into your
final report:

```bash
find . -path ./.venv -prune -o -type f -print | grep -v -E '__pycache__|\.pytest_cache|\.DS_Store|\.cursor' | sort
ls -la dummy-backend/ grafana/provisioning/ 2>&1
docker compose config --services
docker compose config | sed -n '/dummy-backend/,/^  [a-z]/p'
```

Then answer these four questions from what you actually read — do not assume:

- **What is the ASGI app variable called in `dummy-backend/app.py`?** Almost
  certainly `app = FastAPI(...)`, which makes the uvicorn target `app:app`. If
  it is named anything else, your `CMD` must match it.
- **Does `app.py` import anything beyond `fastapi`?** It should only need
  `fastapi` and `uvicorn[standard]`. It does not use `httpx` or
  `prometheus-client`. If you find other third-party imports, add them to
  `requirements.txt` and report it.
- **Is `/burn-cpu` declared `def` or `async def`?** If it is `async def`, its
  busy-loop blocks the event loop, so `/health` and `/calculate` on that replica
  will stall while a burn is in flight. That is arguably realistic pod
  saturation, but it will also make the Docker healthcheck flap. Report which it
  is; do not change it.
- **What `container_name` values do `dummy-backend-1` / `dummy-backend-2` get in
  `docker-compose.yml`?** `prometheus/prometheus.yml` stamps
  `namespace="burstops"` only onto containers matching the regex
  `.*/?burstops-backend-[12]$`. If the container names do not match that regex,
  the gateway's CPU query can never see these containers. Report the exact names
  and whether they match; do not fix `prometheus.yml` yourself.

## 2. `dummy-backend/requirements.txt`

Pin the same versions the gateway already pins, so both images resolve the same
wheels:

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
```

Nothing else unless §1 found extra imports.

## 3. `dummy-backend/Dockerfile`

Mirror `gateway/Dockerfile`'s structure: `python:3.12-slim` base, requirements
copied and installed *before* the app code so the pip layer caches, app code
copied after, port exposed, no build tools left behind.

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8000

# Single worker on purpose: docker-compose caps each replica at cpus: "1.0", and
# one worker saturating one core is what lets /burn-cpu reliably push the
# observed CPU metric past the gateway's 80.0 burst threshold. More workers
# would spread the burn across cores and dilute the signal.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

Two things to get right and verify rather than assume:

- The build context is `./dummy-backend`, so `COPY` can only see files inside
  that directory. `app.py` must stay where it is.
- Read `gateway/Dockerfile` first and match its conventions (base image tag,
  whether it uses a non-root user, `--no-cache-dir`, layer order). If the
  gateway image runs as a non-root user, do the same here and say so.

## 4. `dummy-backend/.dockerignore`

Small but worth it — keeps local tooling out of the image and the build context
small:

```
__pycache__/
*.pyc
.venv/
.pytest_cache/
.DS_Store
nginx.conf
```

`nginx.conf` is listed deliberately: it belongs to the `dummy-backend` nginx VIP
service (which uses the stock `nginx:1.27-alpine` image and bind-mounts the
file), not to the Python replica image.

## 5. `grafana/provisioning/datasources/prometheus.yml`

This is the subtler of the two gaps. Every panel in
`grafana/provisioning/dashboards/burstops.json` is hardcoded to
`"datasource": {"uid": "burstops-prometheus"}`, but no provisioning file anywhere
in the repo creates a datasource with that UID. `dashboard.yml` provisions the
dashboard layout only. The result is a dashboard that loads with six
"datasource not found" panels.

The UID must match exactly — `burstops-prometheus`, not `Prometheus`, not a
Grafana-generated UID.

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    uid: burstops-prometheus       # must match burstops.json's panel datasource uid
    access: proxy
    url: http://prometheus:9090    # compose service name, not localhost
    isDefault: true
    editable: false
    jsonData:
      # prometheus/prometheus.yml scrapes every 2s; telling Grafana this makes
      # $__rate_interval resolve to something sane instead of a 15s default.
      timeInterval: 2s
      httpMethod: POST
```

**Critical check before you trust this file.** Grafana only reads provisioning
from `/etc/grafana/provisioning`. Inspect the `grafana` service's volume mounts
in `docker-compose.yml`:

- If it mounts `./grafana/provisioning` → `/etc/grafana/provisioning`, your new
  `datasources/` subdirectory is picked up automatically. Nothing else to do.
- If it mounts only `./grafana/provisioning/dashboards` →
  `/etc/grafana/provisioning/dashboards`, your file will **never be read**. In
  that case do not silently rewrite the compose file — report the exact current
  mount, state that a second mount line (or broadening the existing one) is
  required, quote the one-line change you propose, and ask before applying it.

## 6. Acceptance — run every one of these and paste the output

A full `docker compose up` still cannot succeed: `dummy-serverless/` and
`cpu-sim/` do not exist yet, and the `gateway` service `depends_on` them. So
bring up an explicit subset by name.

```bash
# 1. Compose file still parses
docker compose config >/dev/null && echo "compose config OK"

# 2. The backend image now builds (this is the gap you just closed)
docker compose build dummy-backend-1 dummy-backend-2

# 3. Bring up only the backend tier plus its nginx VIP
docker compose up -d dummy-backend-1 dummy-backend-2 dummy-backend
docker compose ps

# 4. Health and real work through the VIP
curl -fsS http://localhost:8000/health; echo
curl -fsS http://localhost:8000/calculate | tee /tmp/calc.json; echo

# 5. Round-robin proof: two distinct hostnames across several calls
for i in $(seq 1 6); do curl -fsS http://localhost:8000/calculate \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("hostname"), d.get("source"))'; done

# 6. Prime sieve correctness — must be 168 primes summing to 76127
python3 -c 'import json;d=json.load(open("/tmp/calc.json"));print(d)'

# 7. CPU burn works and is bounded
time curl -fsS -X POST "http://localhost:8000/burn-cpu?ms=1500"; echo

# 8. Grafana picks up the datasource
docker compose up -d prometheus grafana
sleep 8
curl -fsS -u admin:burstops http://localhost:3000/api/datasources | python3 -m json.tool
curl -fsS -u admin:burstops http://localhost:3000/api/datasources/uid/burstops-prometheus | python3 -m json.tool
curl -fsS -u admin:burstops -X POST http://localhost:3000/api/datasources/uid/burstops-prometheus/health
docker compose logs grafana 2>&1 | grep -iE 'provision|datasource|error' | tail -30
```

Pass criteria, all of them:

- Step 2 builds both replicas with no error.
- Step 4 returns HTTP 200 on both endpoints; `/calculate` includes
  `"source": "k8s"`.
- Step 5 prints **two distinct hostnames** across the six calls, proving nginx is
  round-robining rather than pinning one replica.
- Step 6 shows the prime count as **168** and the sum as **76127**. If the JSON
  key names differ, report the actual shape verbatim — later prompts build
  serverless implementations that must mirror this payload.
- Step 7 returns 200 and takes ≳1.5s wall clock.
- Step 8's datasource lookup returns a datasource whose `uid` is exactly
  `burstops-prometheus` and whose `url` is `http://prometheus:9090`; the health
  POST reports success; the logs show no provisioning errors.

Grafana credentials come from `.env` (`GF_SECURITY_ADMIN_USER=admin`,
`GF_SECURITY_ADMIN_PASSWORD=burstops`) — read them from the file rather than
assuming, and do not print the password anywhere except as needed in the curl.

Leave the stack up or tear it down with `docker compose down`, your choice, but
say which you did.

## 7. Stop and ask — do not decide these yourself

- The Grafana provisioning mount does not cover `datasources/` (§5).
- `dummy-backend-1` / `dummy-backend-2` container names don't match the
  `burstops-backend-[12]` regex `prometheus.yml` relabels on.
- `app.py` imports something that needs a dependency beyond fastapi/uvicorn, or
  its ASGI app isn't named `app`.
- You notice that `.env` sets `K8S_UPSTREAM=http://20.219.208.79:8000` — a bare
  IP rather than the portable `http://dummy-backend:8000` that
  `docker-compose.yml`'s own inline default uses. This is a real fragility, but
  it may be deliberate (someone testing against a remote box). **Flag it, quote
  both values, and leave it alone.**
- Anything makes you want to edit a file outside the four in §Scope.

## 8. Report back with

1. The `find` / `ls` output from §1, so the file inventory is on record.
2. Answers to §1's four questions.
3. The four (or three) files you created, in full.
4. Every acceptance command's output, with a pass/fail line per criterion.
5. The exact JSON shape `/calculate` returns — key names matter for prompts 02
   and 04, which build serverless upstreams that must mirror it.
6. Anything you flagged under §7, and anything in the repo that contradicts what
   this prompt told you to expect.

Do not start on `dummy-serverless/`, `cpu-sim/`, the Azure Function, Terraform,
or any gateway change. Those are separate tasks with their own briefs.




