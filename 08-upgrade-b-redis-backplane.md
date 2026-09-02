# PROMPT 08 — Upgrade B: Redis backplane for multi-replica gateways

> Paste this entire file to the coding agent as its task. It is self-contained.

## Your role

You are working on **BurstOps**, a Layer-7 gateway that compensates for
Kubernetes HPA provisioning lag. A poller queries Prometheus every 2s for cluster
CPU; `RoutingState` is a hysteresis state machine entering `BURST` at CPU ≥ 80.0 and
returning to `BASELINE` below 60.0, with a 15s stale-poll grace after which it fails
open to `BURST`. Requests in `BURST` are deflected to an Azure Function over an
HMAC-signed contract.

The gateway currently runs as **exactly one replica**, and Phase 6's
`k8s/gateway-deployment.yaml` carries a comment saying so deliberately. This task
removes that constraint.

## 1. The problem, precisely

`RoutingState` is a single in-memory Python object. Run N replicas and you get N
independent copies:

- **Divergent decisions.** Each replica polls Prometheus on its own 2s cadence with
  its own phase offset. Around a threshold crossing, replica 1 is in `BURST` while
  replica 2 is still `BASELINE`, so identical requests take different upstreams
  depending on which pod the Service happened to pick.
- **Divergent deflection ratios** (if Upgrade A has landed). Each replica runs its
  own PI controller against its own error history and its own integral. The
  aggregate deflection is the mean of N controllers that never agree, and each one
  is tuned for a plant it only partially controls.
- **N× the Prometheus load.** Every replica issues the same range query every 2
  seconds. At 3 replicas that is 90 queries/minute for one number.
- **Meaningless transition metrics.** `gateway_state_transitions_total` sums across
  replicas, so a single real transition reads as N, and flapping in one pod is
  indistinguishable from a cluster-wide event.

The fix is to separate the **control plane** (one poller, one state machine, one
controller) from the **data plane** (N stateless replicas that just route). Redis
carries the decision between them.

## 2. Where Redis comes from — the cost decision

**Do not provision Azure Cache for Redis.** As of early 2026 the Basic, Standard and
Premium tiers are in retirement (announced end-of-life 2028-09-30), and **new
instance creation is blocked for subscriptions that did not already have one before
2026-04-01**. The successor is Azure Managed Redis, which starts well above this
project's entire monthly budget.

Re-verify before acting — this is exactly the kind of fact that moves:

```bash
az redis list -o table 2>&1 | head
az provider show -n Microsoft.Cache --query registrationState -o tsv
az redisenterprise list -o table 2>&1 | head
```

Use **in-cluster Redis**: one `Deployment` running `redis:7-alpine` plus a
`ClusterIP` Service. No persistence, no replication, no PVC. That is not a
compromise — the shared state here is a routing hint that any replica can
reconstruct from Prometheus within one poll cycle, so durability buys nothing and
a PVC would cost money and add a failure mode. Set
`--save ""` and `--appendonly no` explicitly so nobody assumes otherwise, cap it
with `--maxmemory 32mb --maxmemory-policy allkeys-lru`, and give it
`requests: 50m/64Mi`, `limits: 200m/128Mi` — the node is a single `Standard_B2s` and
is already tight.

If the user wants a managed instance anyway, price it first and say the number out
loud before creating it.

## 3. Scope

```
gateway/
├── redis_backplane.py        # new — all Redis interaction lives here
├── gateway.py                # surgical additions only (see §5)
├── gateway_entrypoint.py     # new env vars patched in
└── requirements.txt          # + redis
k8s/
├── redis-deployment.yaml     # new
├── redis-service.yaml        # new
├── gateway-deployment.yaml   # replicas 1 -> 3, REDIS_URL env, comment rewritten
└── kustomization.yaml        # + the two new resources
tests/
└── test_redis_backplane.py   # new, uses a fake Redis (see §7)
docker-compose.scale.yml      # new overlay, for local multi-replica testing
docs/
└── upgrade-b-notes.md        # failover behaviour, degradation modes, tuning
```

Do not modify `tests/test_hysteresis.py`, `tests/test_proportional_deflection.py`,
`.env`, `docker-compose.yml`, `dummy-serverless/`, `azure-function/`, or
`k8s/backend-*.yaml`.

## 4. Verify before you write anything

```bash
grep -n -E 'class RoutingState|def update_from_cpu|BURST_THRESHOLD|RECOVERY_THRESHOLD|STALE_STATE_GRACE|POLL_INTERVAL|deflect_ratio' gateway/gateway.py
grep -n -B5 -A 40 'async def.*poll\|lifespan' gateway/gateway.py
grep -n -B3 -A 25 'FUNCTION_UPSTREAM\|K8S_UPSTREAM' gateway/gateway.py    # the request path
cat gateway/gateway_entrypoint.py gateway/requirements.txt
grep -n 'replicas' k8s/gateway-deployment.yaml
pip index versions redis
pytest tests/ -q
```

Report: whether Upgrade A has landed (does `deflect_ratio` exist?), the exact
lifespan/poller structure you will be wrapping, the concrete `redis` version you
resolved, and a green `pytest tests/ -q` **before** you change anything.

## 5. Architecture — leader polls, followers read

### 5a. Leader election

```python
# acquire: atomic, only succeeds if nobody holds it
ok = await r.set(REDIS_LEADER_KEY, INSTANCE_ID, nx=True, px=REDIS_LEADER_TTL_MS)
```

**Renewal must be a compare-and-set, not `SET ... XX`.** `SET key val XX PX ttl`
succeeds whenever the key exists — it does not check who owns it — so a follower
could silently steal an active lease. Use a Lua script so the check and the extend
are one atomic step:

```lua
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('pexpire', KEYS[1], ARGV[2])
else
  return 0
end
```

A `0` return means "I am no longer the leader" — demote immediately, do not retry
into a second leader. Release on graceful shutdown with the same CAS pattern
(`del` only if the value still matches) so a restart hands over in milliseconds
instead of waiting out the TTL.

`INSTANCE_ID` must be unique per process: `f"{socket.gethostname()}-{os.getpid()}"`,
or the pod name via a `fieldRef` to `metadata.name` plus the pid. Two processes
sharing an ID would each believe they hold the other's lease.

### 5b. What the leader publishes

Only the leader polls Prometheus, feeds `update_from_cpu()`, and runs Upgrade A's
controller. After each cycle it writes the result as a hash:

```
HSET burstops:state
  mode            "burst" | "baseline"
  deflect_ratio   "0.625"
  cpu_observed    "78.4"
  updated_at_ms   "1788193291913"
  leader_id       "burstops-gateway-abc-1"
  generation      "417"
```

`generation` comes from `INCR burstops:generation`, and **followers must ignore any
read whose generation is lower than the highest they have already seen.** That is the
guard against a briefly-resurrected old leader writing a stale decision on top of a
fresh one.

Publish a notification on `burstops:state:updates` after each write so followers
react in milliseconds. **Also have followers poll the hash every second as a
backstop** — Redis pub/sub is fire-and-forget with no replay, so a follower that
misses one message during a reconnect would otherwise stay stale indefinitely. Belt
and braces, and the poll costs nothing.

### 5c. The request path must do zero Redis I/O

This is the one rule that must not bend. Followers keep a **local cached copy** of
`(mode, deflect_ratio)` refreshed by a background task, and the request handler reads
that in-memory value exactly as it does today. Never `await redis.hgetall(...)`
inside the handler — you would add a network round trip to every single request and
make Redis a hard latency dependency for the whole data plane.

Set the client's `socket_timeout` and `socket_connect_timeout` to
`REDIS_SOCKET_TIMEOUT_S` (0.5s default) so a hung Redis stalls only the background
task.

### 5d. Degradation — Redis is a cache, never a dependency

Layer the fallbacks so the existing semantics survive intact:

1. **Fresh shared state** (age ≤ `REDIS_STATE_MAX_AGE_MS`) → use it.
2. **Shared state stale or unreadable** → the follower polls Prometheus itself and
   runs its own state machine. This is exactly today's single-replica behaviour, so
   the worst case of a Redis outage is the behaviour you already shipped.
3. **Its own Prometheus polling also stale past `STALE_STATE_GRACE`** → the existing
   fail-open-to-`BURST` path fires, unchanged.

Consequences to implement deliberately:

- **Redis down at startup must not crash the pod.** Log once at warning, set
  `gateway_redis_up 0`, run in local-polling mode, and keep retrying in the
  background. A gateway that crash-loops because its cache is missing is worse than
  no cache.
- Every Redis call is wrapped so **no exception escapes**; increment
  `gateway_redis_errors_total{op="..."}` and move on.
- `REDIS_URL` empty or unset disables the backplane entirely and the gateway behaves
  precisely as it does today. That is the default, so this upgrade is opt-in and the
  Compose stack keeps working untouched.

### 5e. The honest limitation — write it in the docs

Redis-based leader election is **not** consensus. A leader that pauses (GC, CPU
starvation on a saturated B2s node) past the TTL can still believe it is the leader
while a new one takes over, so two writers can briefly coexist; this is the standard
critique of distributed locks over a single Redis. The `generation` counter bounds
the damage and the state is reconstructible in one poll cycle, so for a soft routing
hint the tradeoff is fine.

Say that in `docs/upgrade-b-notes.md` rather than implying the lock is safe. If
BurstOps ever needed a genuinely exclusive decision, the answer would be a
Kubernetes `Lease` object via the coordination API — which is worth naming as the
alternative and not building here.

## 6. Constants and metrics

| Constant | Default | Why |
|---|---|---|
| `REDIS_URL` | `""` | empty ⇒ backplane off, today's behaviour |
| `REDIS_LEADER_KEY` | `burstops:leader` | |
| `REDIS_STATE_KEY` | `burstops:state` | |
| `REDIS_LEADER_TTL_MS` | `6000` | survives two missed renewals |
| `REDIS_LEADER_RENEW_MS` | `2000` | matches `POLL_INTERVAL` |
| `REDIS_STATE_MAX_AGE_MS` | `10000` | ≈ 5 poll cycles before a follower distrusts it |
| `REDIS_SOCKET_TIMEOUT_S` | `0.5` | a hung Redis must not stall the loop |
| `GATEWAY_INSTANCE_ID` | hostname+pid | must be unique per process |

TTL 6000 renewed every 2000 gives a worst-case failover of about
`TTL + POLL_INTERVAL ≈ 8s`. State that number in the docs; it is the answer to "how
long is routing stale after the leader dies".

New metrics — again, **rename nothing that already exists**:

| Metric | Type | Purpose |
|---|---|---|
| `gateway_is_leader` | Gauge 0/1 | must sum to exactly 1 across replicas |
| `gateway_leader_elections_total` | Counter | churn detector; steady-state should be flat |
| `gateway_redis_up` | Gauge 0/1 | |
| `gateway_redis_errors_total{op}` | Counter | |
| `gateway_shared_state_age_seconds` | Gauge | how stale this replica's copy is |
| `gateway_prometheus_polls_total` | Counter | proves polling is 1× not N× |

`gateway_prometheus_polls_total` is the one that makes §1's "N× the Prometheus load"
claim measurable after the fact. Add it even though it is not strictly required.

## 7. `tests/test_redis_backplane.py` — new file, fake Redis

Match the existing suites' style: no running Redis, no network, injected time. Write
a small in-memory fake supporting exactly what you use — `set(nx=, px=)`, `get`,
`delete`, `hset`, `hgetall`, `incr`, `eval` for the renew script, `publish`, plus a
`fail_next(n)` / `always_fail()` switch and a `advance(ms)` to expire keys. Keeping
the fake honest about TTL expiry is the whole value of the exercise.

Required cases:

1. A lone instance acquires leadership; `gateway_is_leader == 1`.
2. A second instance fails to acquire while the lease is held and becomes a
   follower; the pair's `gateway_is_leader` sums to 1.
3. Renewal by the holder extends the TTL. **Renewal by a non-holder returns 0 and
   does not extend anything** — this is the CAS test, and it is the one that catches
   a naive `SET ... XX` implementation.
4. Lease expiry promotes a follower; `gateway_leader_elections_total` increments
   exactly once.
5. Graceful shutdown releases the lease, and the next instance acquires immediately
   rather than after the TTL.
6. A follower's `(mode, deflect_ratio)` equals what the leader wrote, exactly — not
   approximately, and including `deflect_ratio` if Upgrade A has landed.
7. `updated_at_ms` older than `REDIS_STATE_MAX_AGE_MS` makes the follower fall back
   to local polling, and `gateway_shared_state_age_seconds` reflects the real age.
8. A lower `generation` write is ignored; the follower keeps the newer state.
9. **Redis failing on every call**: both instances behave identically to today
   (local polling), `gateway_redis_errors_total` increments, `gateway_redis_up` is 0,
   and **no exception reaches the request path**. Assert the handler still returns a
   routing decision.
10. `REDIS_URL == ""` → the backplane is never constructed and no Redis call is
    attempted at all.
11. Re-run `tests/test_hysteresis.py` and `tests/test_proportional_deflection.py`
    unmodified; both must stay green.

## 8. Kubernetes changes

`k8s/gateway-deployment.yaml`: `replicas: 1` → `3`, add
`REDIS_URL=redis://burstops-redis.<ns>.svc.cluster.local:6379/0`, and **rewrite the
comment** that currently explains why one replica is mandatory — leaving a stale
comment saying "do not scale this" next to `replicas: 3` is worse than no comment.
Replace it with the new reason it is now safe (one leader, followers read shared
state, Redis outage degrades to per-replica polling).

Also add:

- `podAntiAffinity` (preferred, not required) so replicas spread if a second node
  ever exists. `required` on a single-node cluster leaves two pods `Pending`
  forever — a self-inflicted outage. Use `preferredDuringScheduling`.
- A `PodDisruptionBudget` with `minAvailable: 1`.
- **Check the arithmetic before applying.** 3 gateway replicas at `100m` requests, 2
  backend replicas at `250m`, Redis at `50m`, plus kube-system and Prometheus,
  against ~1.9 allocatable CPU on one `Standard_B2s`. If it does not fit, report the
  numbers and present the options (2 gateway replicas, a second node, trimming
  Prometheus) — do not scale the node pool yourself; it changes the bill.

`redis-deployment.yaml`: single replica, `redis:7-alpine`, args
`["--save","","--appendonly","no","--maxmemory","32mb","--maxmemory-policy","allkeys-lru"]`,
readiness and liveness via `redis-cli ping`, the same hardened `securityContext`
Phase 6 used for the gateway. `redis-service.yaml`: `ClusterIP` on 6379.

**Redis has no authentication in this configuration.** That is acceptable only
because it is `ClusterIP`-only and never exposed through the Ingress — say so
explicitly in your report, and add a `NetworkPolicy` restricting ingress to pods
carrying the gateway's label if the cluster's CNI supports it. Never give Redis a
`LoadBalancer` Service.

## 9. Local multi-replica testing

`docker-compose.yml` publishes the gateway on a fixed host port 8080, so
`--scale gateway=3` fails on a port conflict. Do not edit it. Create a **new**
`docker-compose.scale.yml` overlay that adds a `redis` service and replaces the
gateway's fixed port mapping with an ephemeral one, then:

```bash
docker compose -f docker-compose.yml -f docker-compose.scale.yml up -d --build --scale gateway=3
docker compose -f docker-compose.yml -f docker-compose.scale.yml ps
for p in $(docker compose -f docker-compose.yml -f docker-compose.scale.yml port --index=1 gateway 8080) ; do echo $p; done
```

Then, for each replica, confirm `gateway_is_leader` sums to 1 and that all three
report the same `gateway_routing_mode` and `gateway_deflect_ratio`:

```bash
for i in 1 2 3; do
  P=$(docker compose -f docker-compose.yml -f docker-compose.scale.yml port --index=$i gateway 8080)
  echo "== replica $i ($P)"
  curl -s "http://$P/metrics" | grep -E '^gateway_(is_leader|routing_mode|deflect_ratio|shared_state_age_seconds|prometheus_polls_total)'
done
```

## 10. Acceptance in AKS

```bash
kubectl apply -k k8s/
kubectl -n <gateway-ns> rollout status deploy/burstops-gateway --timeout=180s
kubectl -n <gateway-ns> get pods -l app=burstops-gateway -o wide

# A. exactly one leader
for p in $(kubectl -n <gateway-ns> get pods -l app=burstops-gateway -o name); do
  echo "== $p"; kubectl -n <gateway-ns> exec $p -- \
    python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8080/metrics').read().decode())" \
    | grep -E '^gateway_(is_leader|routing_mode|deflect_ratio|prometheus_polls_total)'
done
# (simpler alternative: port-forward each pod individually and curl it)

# B. followers are not polling Prometheus
#    gateway_prometheus_polls_total should be climbing on ONE pod and flat on the others

# C. failover: delete the leader, time the handover
kubectl -n <gateway-ns> delete pod <leader-pod> --wait=false
# poll all remaining pods every second; record when is_leader==1 reappears
# expect <= REDIS_LEADER_TTL_MS + POLL_INTERVAL  (~8s with the defaults)

# D. agreement under a real transition
#    drive load (Phase 6 §7g), then confirm every replica reports the same mode and
#    the same deflect_ratio to 3 decimal places within ~1s of each other

# E. Redis outage degrades, does not break
kubectl -n <ns> scale deploy/burstops-redis --replicas=0
sleep 20
# every pod: gateway_redis_up 0, errors climbing, routing still correct,
# gateway_prometheus_polls_total now climbing on ALL pods (local fallback)
curl -s <gateway>/calculate | python3 -m json.tool     # still 200, still correct
kubectl -n <ns> scale deploy/burstops-redis --replicas=1
sleep 20
# leadership re-establishes, exactly one leader again, no crash-loops
kubectl -n <gateway-ns> get pods -l app=burstops-gateway   # RESTARTS must be 0

pytest tests/ -q
```

Pass criteria: `gateway_is_leader` sums to exactly 1 at every observation; polls
climb on one pod only; failover completes within the stated bound and
`gateway_leader_elections_total` increments by exactly 1; all replicas agree on mode
and ratio; the Redis outage causes **zero pod restarts** and zero failed requests;
`pytest tests/ -q` green with the two earlier test files unmodified.

## 11. Stop and ask — do not decide these yourself

- Creating **any** managed Redis (Azure Cache for Redis, Azure Managed Redis) or
  anything else with a recurring charge. Price it, state the number, wait.
- Changing `BURST_THRESHOLD`, `RECOVERY_THRESHOLD`, `STALE_STATE_GRACE`, the
  fail-open behaviour, `update_from_cpu`, or any existing metric name or label.
- Modifying `tests/test_hysteresis.py` or `tests/test_proportional_deflection.py`.
- Editing `docker-compose.yml` or `.env` to make local scaling work — use the new
  overlay file.
- Making Redis a hard dependency, or reading Redis in the request path. If the design
  seems to require either, stop; something is wrong.
- 3 replicas plus Redis do not fit on the node. Report the allocation numbers and the
  options; do not add nodes.
- Exposing Redis outside the cluster, or adding a `LoadBalancer` Service for it.
- Replacing Redis leader election with a Kubernetes `Lease`. It is the more correct
  primitive and a reasonable thing to want — but it is a different design, so propose
  it rather than substituting it.

## 12. Report back with

1. §4's verification output, whether Upgrade A had landed, the `redis` version you
   pinned, and the pre-change test result.
2. Unified diffs of `gateway.py`, `gateway_entrypoint.py`, `requirements.txt` and
   `k8s/gateway-deployment.yaml` — plus the full text of every new file.
3. Confirmation that `update_from_cpu`'s mode logic is byte-identical, and that the
   request path performs no Redis I/O (quote the handler).
4. The renewal Lua script, and an explanation in your own words of why
   `SET ... XX PX` would have been wrong.
5. `pytest tests/ -q` output and the new test file in full.
6. §9's three-replica local output and §10's A–E results, with the **measured**
   failover time next to the predicted ~8s.
7. The node allocation arithmetic for 3 gateway replicas + Redis on one B2s.
8. The security posture of the in-cluster Redis stated plainly, and whether you added
   a `NetworkPolicy`.
9. `git diff --stat` proving the protected files are untouched.

Do not implement cost telemetry or tracing. Those are Upgrades C and D.





