# Upgrade B — Redis backplane notes

## What changed

`RoutingState` was a single in-memory object — N replicas = N independent
decisions ("split-brain" mid-transition), N× the Prometheus load, and
transition metrics multiplied by replica count. Now the CONTROL PLANE (one
poller + state machine + PI controller) is separated from the DATA PLANE
(N stateless routers), with Redis carrying the decision between them.

## Architecture

- **Leader election:** `SET burstops:leader <id> NX PX 6000`. Renewal is a
  **Lua compare-and-set** (check owner + pexpire atomically). `SET ... XX`
  would be WRONG: XX succeeds whenever the key *exists* — it never checks
  *who* owns it — so a follower could silently steal an active lease.
  Release on graceful shutdown is the same CAS pattern → handover in
  milliseconds, not TTL. A `0` renew return demotes immediately; a leader
  never retries into a second leader.
- **What the leader publishes:** a hash `burstops:state` {mode,
  deflect_ratio, cpu_observed, updated_at_ms, leader_id, generation}.
  `generation` comes from INCR and followers ignore any read whose
  generation is lower than the highest seen — bounds damage from a
  briefly-resurrected old leader.
- **Pub/sub notify + 1 s poll backstop** (pub/sub is fire-and-forget).
- **THE rule that must not bend:** the request path does ZERO Redis I/O.
  Followers keep a local cached copy refreshed by the background task; the
  handler reads in-memory state exactly as before.
- **Degradation ladder:** fresh shared state → use it; stale/unreadable →
  poll Prometheus yourself (exactly today's single-replica behaviour);
  own polling stale past STALE_STATE_GRACE → existing fail-open-to-BURST.
  Redis down at startup logs ONE warning and retries in background — a
  gateway that crash-loops over a missing cache is worse than no cache.
  `REDIS_URL` empty (default) disables the whole thing.

## Constants

`REDIS_LEADER_TTL_MS=6000`, `REDIS_LEADER_RENEW_MS=2000` (matches
POLL_INTERVAL), `REDIS_STATE_MAX_AGE_MS=10000` (~5 poll cycles),
`REDIS_SOCKET_TIMEOUT_S=0.5`.

**Worst-case failover after leader death: TTL + one renew interval ≈ 8 s.**
Measured live (3 replicas, `docker rm -f` the leader): **4 s**.

## The honest limitation — this is NOT consensus

A leader that pauses (GC, CPU starvation) past its TTL can still believe it
leads while another takes over: two writers can briefly coexist. This is
the standard critique of distributed locks over a single Redis. For a
*soft routing hint* that any replica can reconstruct within one poll
cycle, the tradeoff is fine. If BurstOps ever needed a genuinely exclusive
decision, the answer is a Kubernetes `Lease` object via the coordination
API — deliberately not built (a different design; propose, don't
substitute).

## Live acceptance (2026-09-01, 3 replicas + redis:7-alpine)

- **A:** `gateway_is_leader` sums to exactly 1; `gateway_prometheus_polls_total`
  climbs on ONE pod only (followers: 0) — the N×-load claim, now measured.
- **C:** leader deleted → new leader in **4 s** (bound 8 s);
  `gateway_leader_elections_total` incremented exactly once.
- **D:** all replicas report identical mode + deflect_ratio.
- **E:** Redis stopped → `gateway_redis_up 0`, per-op error counters
  climbing, polls resumed on ALL pods (local fallback), requests still 200,
  **zero pod restarts**; Redis back → exactly one leader again.

## Security posture

Redis is unauthenticated BY DESIGN in this scope: ClusterIP-equivalent
network only (compose internal), never exposed through any ingress, no
persistence, maxmemory 32mb allkeys-lru. On AKS the next hardening step
would be a NetworkPolicy restricting ingress to gateway-labelled pods +
TLS via cert rotation. Never give this Redis a LoadBalancer.

## Where it runs

Per the Option B architecture decision (docs/architecture-decision.md),
multi-replica is demonstrated via the local overlay
`docker-compose.scale.yml` (`--scale gateway=3`), not AKS. The
`k8s/redis-*.yaml` manifests for AKS remain a future addition under the
reversal path.
