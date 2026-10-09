import asyncio
import logging
import random
import time
from typing import Any, Callable, Dict, Optional, Tuple
import httpx

from backend.config import settings

logger = logging.getLogger("burstops.adapter")


class BaseTrafficAdapter:
    async def start_traffic(self, log_cb: Callable[[str, str], None]) -> bool:
        raise NotImplementedError

    async def poll_health(self) -> Tuple[Optional[str], float]:
        """Returns (mode, cpu_percent)."""
        raise NotImplementedError

    async def test_calculate(self) -> Optional[Dict[str, Any]]:
        """Sends a single test request through the gateway to sample current routing."""
        raise NotImplementedError

    async def stop_traffic(self, log_cb: Callable[[str, str], None]) -> bool:
        raise NotImplementedError

    async def cleanup(self) -> None:
        pass


class CloudTrafficAdapter(BaseTrafficAdapter):
    """Interacts with the real deployed Azure cluster and public gateway.

    Uses:
    1. The in-cluster Locust ingress endpoint (/locust/swarm, /locust/stop) to trigger load.
    2. Concurrent HTTP requests to the public gateway (/calculate) to exercise the gateway.
    3. The public gateway /health endpoint to monitor CPU and hysteresis mode.
    """

    def __init__(self):
        self.gateway_base = settings.GATEWAY_BASE_URL.rstrip("/")
        self.locust_base = settings.LOCUST_INGRESS_URL.rstrip("/")
        self._http_workers_running = False
        self._worker_tasks: list[asyncio.Task] = []
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def start_traffic(self, log_cb: Callable[[str, str], None]) -> bool:
        client = self._get_client()
        log_cb("INFO", f"Connecting to live Azure cluster at {self.gateway_base}...")

        # 1. Start in-cluster Locust traffic generator via public Ingress API
        locust_started = False
        try:
            swarm_url = f"{self.locust_base}/swarm"
            log_cb("INFO", f"Triggering in-cluster load generator via {swarm_url} (20 users, spawn rate 5)...")
            resp = await client.post(
                swarm_url,
                data={"user_count": 20, "spawn_rate": 5},
                timeout=8.0,
            )
            if resp.status_code in (200, 201, 204):
                locust_started = True
                log_cb("SUCCESS", f"In-cluster Locust swarm engaged (HTTP {resp.status_code}).")
            else:
                log_cb("WARN", f"Locust swarm returned HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as exc:
            log_cb("WARN", f"In-cluster Locust trigger notice: {exc}. Will proceed with direct gateway workload.")

        # 2. Start concurrent external traffic workers to the gateway /calculate endpoint
        self._http_workers_running = True
        self._worker_tasks = []
        log_cb("INFO", f"Launching {settings.CONCURRENT_HTTP_WORKERS} concurrent HTTP generator workers against /calculate...")

        for worker_id in range(settings.CONCURRENT_HTTP_WORKERS):
            task = asyncio.create_task(self._worker_loop(worker_id))
            self._worker_tasks.append(task)

        return True

    async def _worker_loop(self, worker_id: int):
        """Worker sending sustained traffic to the gateway /calculate endpoint."""
        client = httpx.AsyncClient(timeout=8.0)
        url = f"{self.gateway_base}/calculate"
        try:
            while self._http_workers_running:
                try:
                    await client.post(url, json={"max_num": 1000})
                except Exception:
                    pass
                # Small jitter to prevent lockstep flooding
                await asyncio.sleep(random.uniform(0.05, 0.2))
        finally:
            await client.aclose()

    async def poll_health(self) -> Tuple[Optional[str], float]:
        client = self._get_client()
        url = f"{self.gateway_base}/health"
        try:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                mode = data.get("mode")
                cpu = float(data.get("last_cpu", 0.0))
                return mode, cpu
        except Exception as exc:
            logger.debug("Failed to poll health: %s", exc)
        return None, 0.0

    async def test_calculate(self) -> Optional[Dict[str, Any]]:
        client = self._get_client()
        url = f"{self.gateway_base}/calculate"
        try:
            resp = await client.post(url, json={"max_num": 1000}, timeout=10.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as exc:
            logger.warning("Calculation sample failed: %s", exc)
        return None

    async def stop_traffic(self, log_cb: Callable[[str, str], None]) -> bool:
        log_cb("INFO", "Halting active traffic generator workers...")
        self._http_workers_running = False

        # Cancel worker tasks
        for t in self._worker_tasks:
            t.cancel()
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
            self._worker_tasks.clear()
        log_cb("INFO", "All concurrent HTTP workers stopped.")

        # Stop in-cluster Locust swarm
        client = self._get_client()
        try:
            stop_url = f"{self.locust_base}/stop"
            log_cb("INFO", f"Signaling in-cluster Locust to stop via {stop_url}...")
            resp = await client.get(stop_url, timeout=8.0)
            if resp.status_code in (200, 204):
                log_cb("SUCCESS", f"In-cluster load stopped successfully (HTTP {resp.status_code}).")
            else:
                log_cb("WARN", f"Locust stop returned HTTP {resp.status_code}.")
        except Exception as exc:
            log_cb("WARN", f"Notice while signaling Locust stop: {exc}")

        return True

    async def cleanup(self) -> None:
        self._http_workers_running = False
        for t in self._worker_tasks:
            t.cancel()
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class MockTrafficAdapter(BaseTrafficAdapter):
    """High-fidelity mock adapter for automated tests and offline verification.

    Simulates the exact timing, PromQL smoothing curve, and canary responses
    without connecting to external networks.
    """

    def __init__(self):
        self.is_running = False
        self.mode = "baseline"
        self.cpu = 15.0
        self.tick = 0

    async def start_traffic(self, log_cb: Callable[[str, str], None]) -> bool:
        self.is_running = True
        self.tick = 0
        log_cb("INFO", "[MOCK] Load generator started against simulated gateway.")
        log_cb("INFO", "[MOCK] Generating steady traffic to exercise Sieve prime calculation...")
        return True

    async def poll_health(self) -> Tuple[Optional[str], float]:
        if self.is_running:
            self.tick += 1
            if self.tick >= 2:
                self.cpu = min(94.2, 50.0 + self.tick * 15.0)
            if self.cpu >= 80.0:
                self.mode = "burst"
        else:
            if self.cpu > 20.0:
                self.cpu = max(18.0, self.cpu - 25.0)
            if self.cpu <= 60.0:
                self.mode = "baseline"
        return self.mode, self.cpu

    async def test_calculate(self) -> Optional[Dict[str, Any]]:
        if self.mode == "burst":
            return {
                "source": "serverless",
                "impl": "azure-function",
                "instance_id": "mock77aa",
                "prime_count": 168,
                "prime_sum": 76127,
                "cold_start": False,
            }
        return {
            "source": "k8s",
            "impl": "dummy-backend",
            "hostname": "burstops-backend-mock-9b8f",
            "prime_count": 168,
            "prime_sum": 76127,
        }

    async def stop_traffic(self, log_cb: Callable[[str, str], None]) -> bool:
        self.is_running = False
        log_cb("INFO", "[MOCK] Traffic stopped. Allowing CPU cooling down...")
        return True

    async def cleanup(self) -> None:
        self.is_running = False


def get_adapter() -> BaseTrafficAdapter:
    if settings.DEMO_MODE.lower() == "mock":
        return MockTrafficAdapter()
    return CloudTrafficAdapter()
