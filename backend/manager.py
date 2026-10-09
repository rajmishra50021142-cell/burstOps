import asyncio
import datetime
import logging
import re
import time
import uuid
from typing import Dict, List, Optional

from backend.adapter import BaseTrafficAdapter, get_adapter
from backend.config import settings
from backend.models import (
    ActionState,
    CalculationCanary,
    DemoStatusResponse,
    LogEntry,
    LogLevel,
    OrderedLink,
    RunDetail,
)

logger = logging.getLogger("burstops.manager")

# Patterns for sensitive token redaction
REDACTION_PATTERNS = [
    re.compile(r"(?i)(key|secret|password|token|code)=([A-Za-z0-9+/_=-]{8,})"),
    re.compile(r"(?i)(authorization|x-functions-key|x-gateway-signature):\s*([^\s]+)"),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._-]+"),
]


def redact_text(text: str) -> str:
    """Masks secrets, tokens, and sensitive headers from console logs."""
    res = text
    for pat in REDACTION_PATTERNS:
        res = pat.sub(r"\1=***REDACTED***", res)
    return res


class DemoRunManager:
    def __init__(self, adapter: Optional[BaseTrafficAdapter] = None):
        self.adapter = adapter or get_adapter()
        self.lock = asyncio.Lock()
        self.active_run: Optional[RunDetail] = None
        self.last_completed_run: Optional[RunDetail] = None
        self.last_run_end_time: float = 0.0
        self._current_task: Optional[asyncio.Task] = None
        self._recovery_requested = asyncio.Event()

    def _append_log(self, run: RunDetail, level: LogLevel, message: str) -> None:
        now = time.time()
        iso = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc).strftime("%H:%M:%S")
        safe_msg = redact_text(message)
        entry = LogEntry(timestamp=now, iso_time=iso, level=level, message=safe_msg)
        run.logs.append(entry)
        # Cap memory buffer at 500 lines per run
        if len(run.logs) > 500:
            run.logs.pop(0)
        logger.info("[%s] [%s] %s", run.run_id[:8], level.value, safe_msg)

    def get_ordered_links(self, is_recovery: bool) -> List[OrderedLink]:
        sub_id = settings.AZURE_SUBSCRIPTION_ID
        rg = settings.AZURE_RESOURCE_GROUP
        aks = settings.AZURE_AKS_CLUSTER
        func = settings.AZURE_FUNCTION_APP
        app_insights = settings.AZURE_APP_INSIGHTS

        portal_prefix = f"https://portal.azure.com/#@/resource/subscriptions/{sub_id}/resourceGroups/{rg}"

        links = [
            OrderedLink(
                number=1,
                title="Gateway Health & Mode",
                url=f"{settings.GATEWAY_BASE_URL.rstrip('/')}/health",
                description="Live JSON health check showing active state machine mode ('baseline' or 'burst') and Prometheus-polled CPU percentage.",
            ),
            OrderedLink(
                number=2,
                title="Grafana — BurstOps Dashboard",
                url=settings.GRAFANA_URL,
                description="Live 12-panel dashboard displaying real-time CPU curves, deflection ratio, request distribution, and FinOps metrics.",
            ),
            OrderedLink(
                number=3,
                title="Prometheus Metrics",
                url=settings.PROMETHEUS_URL,
                description="Raw Prometheus metrics exporter exposing gateway_routing_mode, gateway_cpu_observed_percent, and latency histograms.",
            ),
            OrderedLink(
                number=4,
                title="AKS Cluster & Workloads",
                url=f"{portal_prefix}/providers/Microsoft.ContainerService/managedClusters/{aks}/workloads",
                description="Azure Portal view of the Kubernetes cluster, showing healthy pods across burstops, burstops-system, and monitoring namespaces.",
            ),
            OrderedLink(
                number=5,
                title="Backend Deployment & HPA",
                url=f"{portal_prefix}/providers/Microsoft.ContainerService/managedClusters/{aks}/overview",
                description="Examines the primary Kubernetes backend replicas and Horizontal Pod Autoscaler status.",
            ),
            OrderedLink(
                number=6,
                title="Azure Function App",
                url=f"{portal_prefix}/providers/Microsoft.Web/sites/{func}",
                description="Azure Portal overview of the Flex Consumption Python 3.13 serverless burst target.",
            ),
            OrderedLink(
                number=7,
                title="Application Insights / Monitoring",
                url=f"{portal_prefix}/providers/Microsoft.OperationalInsights/workspaces/{app_insights}",
                description="Telemetry, execution counts, serverless latency charts, and live log streams.",
            ),
            OrderedLink(
                number=8,
                title="Azure Resource Group Overview",
                url=f"{portal_prefix}/overview",
                description="Complete infrastructure overview in Azure region centralindia.",
            ),
        ]
        return links

    async def get_status(self) -> DemoStatusResponse:
        async with self.lock:
            state = ActionState.READY
            active_id = None
            can_burst = True
            can_recover = False

            # Check cooldown
            since_last = time.time() - self.last_run_end_time
            in_cooldown = since_last < settings.COOLDOWN_SECONDS

            if self.active_run:
                state = self.active_run.state
                active_id = self.active_run.run_id
                can_burst = False
                can_recover = self.active_run.state in (
                    ActionState.STARTING,
                    ActionState.RUNNING,
                    ActionState.BURST_DETECTED,
                    ActionState.DEFLECTION_VERIFIED,
                )
            elif in_cooldown:
                can_burst = False

            # Decide heading
            is_rec = False
            if self.active_run:
                is_rec = self.active_run.recovery_started
            elif self.last_completed_run:
                is_rec = self.last_completed_run.recovery_started

            heading = "Verify Recovery in Azure" if is_rec else "Inspect the Burst in Azure"
            links = self.get_ordered_links(is_recovery=is_rec)

            return DemoStatusResponse(
                state=state,
                active_run_id=active_id,
                can_burst=can_burst,
                can_recover=can_recover,
                current_run=self.active_run,
                last_completed_run=self.last_completed_run,
                links_heading=heading,
                ordered_links=links,
            )

    async def start_burst(self) -> RunDetail:
        async with self.lock:
            if self.active_run is not None:
                raise ValueError("An active demonstration run is already in progress.")

            since_last = time.time() - self.last_run_end_time
            if since_last < settings.COOLDOWN_SECONDS:
                remaining = int(settings.COOLDOWN_SECONDS - since_last)
                raise ValueError(f"System in cooldown. Please wait {remaining} seconds before starting a new run.")

            run_id = f"run-{uuid.uuid4().hex[:8]}"
            now = time.time()
            self._recovery_requested.clear()

            run = RunDetail(
                run_id=run_id,
                state=ActionState.STARTING,
                created_at=now,
                started_at=now,
            )
            self.active_run = run
            self._append_log(run, LogLevel.INFO, f"Initiating BurstOps demonstration run {run_id}...")

            # Launch monitoring worker task
            self._current_task = asyncio.create_task(self._burst_lifecycle_worker(run))
            return run

    async def _burst_lifecycle_worker(self, run: RunDetail):
        try:
            # 1. Connect and start traffic
            def log_cb(lvl: str, msg: str):
                level_enum = getattr(LogLevel, lvl.upper(), LogLevel.INFO)
                self._append_log(run, level_enum, msg)

            started = await self.adapter.start_traffic(log_cb)
            if not started:
                run.state = ActionState.FAILED
                run.error_message = "Failed to start traffic generator."
                self._append_log(run, LogLevel.ERROR, run.error_message)
                return

            run.state = ActionState.RUNNING
            self._append_log(run, LogLevel.INFO, "Traffic generator running. Monitoring CPU ramp and hysteresis state machine...")

            # 2. Monitor for burst transition
            start_t = time.time()
            burst_seen = False

            while not self._recovery_requested.is_set():
                elapsed = time.time() - start_t
                run.elapsed_seconds = round(elapsed, 1)

                if elapsed > settings.MAX_RUN_DURATION_SECONDS:
                    run.state = ActionState.TIMED_OUT
                    self._append_log(
                        run,
                        LogLevel.WARN,
                        f"Safety limit reached ({settings.MAX_RUN_DURATION_SECONDS}s). Auto-triggering recovery...",
                    )
                    await self._execute_recovery(run)
                    return

                mode, cpu = await self.adapter.poll_health()
                if mode is not None:
                    self._append_log(
                        run,
                        LogLevel.INFO,
                        f"Telemetry poll: Mode={mode.upper()} | Backend CPU={cpu:5.1f}% (Threshold: 80% burst / 60% recovery)",
                    )
                    if mode.lower() == "burst" and not burst_seen:
                        burst_seen = True
                        run.burst_detected = True
                        run.state = ActionState.BURST_DETECTED
                        self._append_log(
                            run,
                            LogLevel.SUCCESS,
                            ">>> BURST THRESHOLD EXCEEDED (CPU ≥ 80%)! Gateway entered BURST mode! <<<",
                        )

                        # Test calculation deflection canary
                        sample = await self.adapter.test_calculate()
                        if sample:
                            canary = CalculationCanary(
                                source=sample.get("source", "unknown"),
                                impl=sample.get("impl", "unknown"),
                                hostname=sample.get("hostname"),
                                instance_id=sample.get("instance_id"),
                                prime_count=sample.get("prime_count", 0),
                                prime_sum=sample.get("prime_sum", 0),
                                cold_start=sample.get("cold_start"),
                            )
                            run.burst_canary = canary
                            if canary.source == "serverless":
                                run.serverless_verified = True
                                run.state = ActionState.DEFLECTION_VERIFIED
                                self._append_log(
                                    run,
                                    LogLevel.SUCCESS,
                                    f"SERVERLESS DEFLECTION CONFIRMED: source={canary.source}, impl={canary.impl}, "
                                    f"instance={canary.instance_id}, primes={canary.prime_count} (sum={canary.prime_sum})",
                                )
                            else:
                                self._append_log(
                                    run,
                                    LogLevel.INFO,
                                    f"Gateway in BURST mode (PI deflection active). Sample routed to: {canary.source}",
                                )

                await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)

            # If user explicitly requested recovery, execute it
            await self._execute_recovery(run)

        except asyncio.CancelledError:
            run.state = ActionState.CANCELLED
            self._append_log(run, LogLevel.WARN, "Operation was cancelled.")
            await self.adapter.cleanup()
        except Exception as exc:
            run.state = ActionState.FAILED
            run.error_message = str(exc)
            self._append_log(run, LogLevel.ERROR, f"Error in run execution: {exc}")
            await self.adapter.cleanup()
        finally:
            run.ended_at = time.time()
            self.last_run_end_time = run.ended_at
            async with self.lock:
                self.last_completed_run = run
                self.active_run = None

    async def start_recovery(self) -> RunDetail:
        async with self.lock:
            if self.active_run is None:
                raise ValueError("No active demonstration run to recover.")
            if self.active_run.recovery_started:
                return self.active_run

            self.active_run.recovery_started = True
            self.active_run.state = ActionState.RECOVERY_IN_PROGRESS
            self._append_log(
                self.active_run,
                LogLevel.INFO,
                "User clicked 'Recover to Baseline'. Initiating graceful recovery sequence...",
            )
            self._recovery_requested.set()
            return self.active_run

    async def _execute_recovery(self, run: RunDetail):
        run.recovery_started = True
        run.state = ActionState.RECOVERY_IN_PROGRESS

        def log_cb(lvl: str, msg: str):
            level_enum = getattr(LogLevel, lvl.upper(), LogLevel.INFO)
            self._append_log(run, level_enum, msg)

        # 1. Stop active load generator
        await self.adapter.stop_traffic(log_cb)
        self._append_log(
            run,
            LogLevel.INFO,
            "Traffic generation stopped. Observing natural CPU decay below 60% recovery threshold...",
        )

        # 2. Wait for CPU to decay below 60% and mode to return to baseline
        rec_start = time.time()
        baseline_observed = False

        while time.time() - rec_start < settings.RECOVERY_TIMEOUT_SECONDS:
            await asyncio.sleep(settings.RECOVERY_POLL_INTERVAL_SECONDS)
            mode, cpu = await self.adapter.poll_health()
            if mode is not None:
                self._append_log(
                    run,
                    LogLevel.INFO,
                    f"Cooling poll: Mode={mode.upper()} | Backend CPU={cpu:5.1f}% (Recovery Target: < 60%)",
                )
                if mode.lower() == "baseline" and cpu < 60.0:
                    baseline_observed = True
                    break

        if baseline_observed:
            run.baseline_verified = True
            run.state = ActionState.BASELINE_VERIFIED
            self._append_log(
                run,
                LogLevel.SUCCESS,
                ">>> RECOVERY CONFIRMED: Gateway returned to BASELINE mode! <<<",
            )
            # Canary test
            sample = await self.adapter.test_calculate()
            if sample:
                canary = CalculationCanary(
                    source=sample.get("source", "unknown"),
                    impl=sample.get("impl", "unknown"),
                    hostname=sample.get("hostname"),
                    instance_id=sample.get("instance_id"),
                    prime_count=sample.get("prime_count", 0),
                    prime_sum=sample.get("prime_sum", 0),
                )
                run.recovery_canary = canary
                self._append_log(
                    run,
                    LogLevel.SUCCESS,
                    f"BASELINE VERIFICATION CANARY: source={canary.source}, impl={canary.impl}, "
                    f"host={canary.hostname}, primes={canary.prime_count} (sum={canary.prime_sum})",
                )
        else:
            run.state = ActionState.TIMED_OUT
            self._append_log(
                run,
                LogLevel.WARN,
                f"Recovery timeout ({settings.RECOVERY_TIMEOUT_SECONDS}s). CPU did not decay below 60% in time.",
            )

    async def get_run(self, run_id: str) -> Optional[RunDetail]:
        if self.active_run and self.active_run.run_id == run_id:
            return self.active_run
        if self.last_completed_run and self.last_completed_run.run_id == run_id:
            return self.last_completed_run
        return None
