"""Locust load generator for BurstOps.

BurstOpsUser mixes two weighted tasks:
 - 95%: GET /calculate — organic traffic through the gateway.
 - 5%: POST /burn-cpu?ms=<1500|2000|2500> — sent directly to the
   dummy-backend VIP (the gateway only proxies /calculate), so cAdvisor
   sees real CPU load on the backend replicas.
"""
import random

from locust import HttpUser, between, task


class BurstOpsUser(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self):
        print(
            "\n=== BurstOps load test ===\n"
            "Grafana dashboard: http://localhost:3000 (admin)\n"
            "Manual burst trigger: curl -X POST http://localhost:8002/ramp-up\n"
            "Gateway health:      curl http://localhost:8080/health\n"
        )

    @task(95)
    def calculate(self):
        self.client.get("/calculate")

    @task(5)
    def burn_cpu(self):
        # sent directly to the backend VIP — the gateway only proxies /calculate
        backend = self.environment.host.replace("http://gateway:8080", "http://dummy-backend:8000")
        ms = random.choice([1500, 2000, 2500])
        try:
            self.client.post(f"{backend}/burn-cpu?ms={ms}", name="/burn-cpu")
        except Exception:
            pass
