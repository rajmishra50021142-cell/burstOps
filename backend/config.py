import os
from pydantic import BaseModel, Field


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

    # Safety, Cooldown, and Limits
    MAX_RUN_DURATION_SECONDS: int = Field(default=int(os.getenv("MAX_RUN_DURATION_SECONDS", "120")))
    RECOVERY_TIMEOUT_SECONDS: int = Field(default=int(os.getenv("RECOVERY_TIMEOUT_SECONDS", "60")))
    COOLDOWN_SECONDS: int = Field(default=int(os.getenv("COOLDOWN_SECONDS", "5")))
    CONCURRENT_HTTP_WORKERS: int = Field(default=int(os.getenv("CONCURRENT_HTTP_WORKERS", "8")))
    POLL_INTERVAL_SECONDS: float = Field(default=float(os.getenv("POLL_INTERVAL_SECONDS", "2.0")))
    RECOVERY_POLL_INTERVAL_SECONDS: float = Field(default=float(os.getenv("RECOVERY_POLL_INTERVAL_SECONDS", "2.0")))


settings = Settings()
