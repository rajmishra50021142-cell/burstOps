"""BurstOps cost model — pure functions, stdlib only, no I/O.

Unit-testable without FastAPI/Prometheus/Azure, exactly like hmac_util.py.

THE ACCOUNTING (read before "fixing" anything):
The AKS node bill is SUNK — deflection does not refund it. At the margin a
deflected request COSTS MORE (list price) than one served on Kubernetes:
~1.75x with this project's numbers. What bursting buys is (1) availability
during HPA provisioning lag, when no Kubernetes capacity exists at any
price, (2) avoided scale-out if overflow is small/short, (3) avoided SLO
breach (not monetized). Therefore NO gateway_cost_saved_* metric exists.

Azure billing rules that materially change the number:
 - Minimum billable duration is 100 ms (a 30 ms invocation bills as 100).
 - Memory is rounded UP to the nearest 128 MB of observed usage.

Note: the Consumption free grant (~1M executions + 400k GB-s/month) means
the actual invoice at demo volume is very likely $0. These metrics report
LIST price — the right thing for a control-plane signal.
"""
import math

# Defaults — the golden vectors in tests/test_costing.py depend on EXACTLY
# these; changing any constant means changing the vectors, deliberately.
EXECUTION_PRICE_USD = 0.20 / 1e6        # per execution
GB_SECOND_PRICE_USD = 0.000016          # per GB-second
MIN_BILLABLE_SECONDS = 0.1              # 100 ms floor
FUNCTION_MEMORY_MB = 128.0              # Python worker realistic floor
NODE_HOURLY_USD = 0.0416                # one Standard_B2s, ~$30.37/mo @730h
CLUSTER_CAPACITY_RPS = 50.0             # assumed saturation of 2 replicas —
                                        # a MODELLING ASSUMPTION, not a
                                        # measurement; correct via Locust ramp
HPA_LAG_WINDOW_SECONDS = 120.0           # burst-episode start window


def kubernetes_cost_per_request(
    node_hourly_usd: float = NODE_HOURLY_USD,
    capacity_rps: float = CLUSTER_CAPACITY_RPS,
) -> float:
    """Amortized node cost per request. Sunk, but needed for comparison."""
    if capacity_rps <= 0:
        raise ValueError("capacity_rps must be > 0")
    return node_hourly_usd / (3600.0 * capacity_rps)


def serverless_cost_per_request_raw(
    duration_s: float,
    memory_mb: float = FUNCTION_MEMORY_MB,
) -> float:
    """Linear model, no 100 ms floor — for golden-vector testing."""
    if duration_s < 0:
        duration_s = 0.0
    billable_mb = 128.0 * math.ceil(memory_mb / 128.0) if memory_mb > 0 else 128.0
    return EXECUTION_PRICE_USD + (billable_mb / 1000.0) * duration_s * GB_SECOND_PRICE_USD


def serverless_cost_per_request(
    duration_s: float,
    memory_mb: float = FUNCTION_MEMORY_MB,
) -> float:
    """Azure Functions Consumption list price: per execution + per GB-second,
    with the 100 ms minimum and 128 MB memory rounding applied."""
    if duration_s < 0:
        duration_s = 0.0
    billable_s = max(duration_s, MIN_BILLABLE_SECONDS)
    return serverless_cost_per_request_raw(billable_s, memory_mb)


def burst_premium_per_request(
    duration_s: float,
    node_hourly_usd: float = NODE_HOURLY_USD,
    capacity_rps: float = CLUSTER_CAPACITY_RPS,
    memory_mb: float = FUNCTION_MEMORY_MB,
) -> float:
    """(serverless - k8s): what bursting cost EXTRA per deflected request."""
    return serverless_cost_per_request(duration_s, memory_mb) - kubernetes_cost_per_request(
        node_hourly_usd, capacity_rps
    )


def breakeven_overflow_rps(
    node_hourly_usd: float = NODE_HOURLY_USD,
    duration_s: float = MIN_BILLABLE_SECONDS,
    memory_mb: float = FUNCTION_MEMORY_MB,
) -> float:
    """Sustained overflow rate at which deflecting costs more than adding a
    whole node. Caveat: Azure VMs bill per second, so the node only wins for
    SUSTAINED overflow; short spikes favor the Function regardless because
    a node cannot be provisioned fast enough to help at all — which is the
    entire premise of BurstOps."""
    if node_hourly_usd <= 0:
        raise ValueError("node_hourly_usd must be > 0")
    per_request = serverless_cost_per_request(duration_s, memory_mb)
    if per_request <= 0:
        raise ValueError("serverless cost must be > 0")
    return node_hourly_usd / (3600.0 * per_request)
