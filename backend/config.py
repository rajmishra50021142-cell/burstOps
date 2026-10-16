import os
from pathlib import Path
from pydantic import BaseModel, Field

# Load optional .env.azure if available and not already in environment
_env_azure = Path(__file__).resolve().parent.parent / ".env.azure"
if _env_azure.exists():
    try:
        with open(_env_azure, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip()
                    if _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass


class Settings(BaseModel):
    # Operating Mode: "cloud" or "mock"
    DEMO_MODE: str = Field(default=os.getenv("DEMO_MODE", "cloud"))

    # Public Azure Endpoints
    GATEWAY_BASE_URL: str = Field(
        default=os.getenv("GATEWAY_BASE_URL", "http://burstops-cloud-ga3cvf.centralindia.cloudapp.azure.com")
    )
    LOCUST_INGRESS_URL: str = Field(
        default=os.getenv("LOCUST_INGRESS_URL", "http://burstops-cloud-ga3cvf.centralindia.cloudapp.azure.com/locust")
    )
    GRAFANA_URL: str = Field(
        default=os.getenv("GRAFANA_URL", "http://burstops-cloud-ga3cvf.centralindia.cloudapp.azure.com/grafana/")
    )
    PROMETHEUS_URL: str = Field(
        default=os.getenv("PROMETHEUS_URL", "http://burstops-cloud-ga3cvf.centralindia.cloudapp.azure.com/metrics")
    )

    # Azure Portal Metadata & Deep Links
    AZURE_SUBSCRIPTION_ID: str = Field(
        default=os.getenv("AZURE_SUBSCRIPTION_ID", "980e5d74-260c-49bc-ba07-2343e710859d")
    )
    AZURE_RESOURCE_GROUP: str = Field(
        default=os.getenv("AZURE_RESOURCE_GROUP", "rg-burstops-prod")
    )
    AZURE_AKS_CLUSTER: str = Field(
        default=os.getenv("AZURE_AKS_CLUSTER", "aks-burstops-ga3cvf")
    )
    AZURE_FUNCTION_APP: str = Field(
        default=os.getenv("AZURE_FUNCTION_APP", "func-burstops-cloud-ga3cvf")
    )
    AZURE_APP_INSIGHTS: str = Field(
        default=os.getenv("AZURE_APP_INSIGHTS", "log-burstops-ga3cvf")
    )

    # Serverless Deflection & Upstream Keys
    FUNCTION_UPSTREAM: str = Field(
        default=os.getenv("FUNCTION_UPSTREAM", "https://func-burstops-cloud-ga3cvf.azurewebsites.net/api/calculate")
    )
    FUNCTION_KEY: str = Field(
        default=os.getenv("FUNCTION_KEY", "local-dev-function-key")
    )
    GATEWAY_HMAC_SECRET: str = Field(
        default=os.getenv("GATEWAY_HMAC_SECRET", "local-dev-secret-change-in-prod")
    )
    REDIS_URL: str = Field(
        default=os.getenv("REDIS_URL", "")
    )

    # Safety, Cooldown, and Limits
    MAX_RUN_DURATION_SECONDS: int = Field(default=int(os.getenv("MAX_RUN_DURATION_SECONDS", "120")))
    RECOVERY_TIMEOUT_SECONDS: int = Field(default=int(os.getenv("RECOVERY_TIMEOUT_SECONDS", "60")))
    COOLDOWN_SECONDS: int = Field(default=int(os.getenv("COOLDOWN_SECONDS", "5")))
    CONCURRENT_HTTP_WORKERS: int = Field(default=int(os.getenv("CONCURRENT_HTTP_WORKERS", "8")))
    POLL_INTERVAL_SECONDS: float = Field(default=float(os.getenv("POLL_INTERVAL_SECONDS", "2.0")))
    RECOVERY_POLL_INTERVAL_SECONDS: float = Field(default=float(os.getenv("RECOVERY_POLL_INTERVAL_SECONDS", "2.0")))


settings = Settings()
