from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ActionState(str, Enum):
    READY = "Ready"
    STARTING = "Starting"
    RUNNING = "Running"
    BURST_DETECTED = "Burst detected"
    DEFLECTION_VERIFIED = "Serverless deflection verified"
    RECOVERY_IN_PROGRESS = "Recovery in progress"
    BASELINE_VERIFIED = "Baseline verified"
    FAILED = "Failed"
    TIMED_OUT = "Timed out"
    CANCELLED = "Cancelled"


class LogLevel(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


class LogEntry(BaseModel):
    timestamp: float
    iso_time: str
    level: LogLevel
    message: str


class CalculationCanary(BaseModel):
    source: str
    impl: str
    hostname: Optional[str] = None
    instance_id: Optional[str] = None
    prime_count: int
    prime_sum: int
    cold_start: Optional[bool] = None


class OrderedLink(BaseModel):
    number: int
    title: str
    url: str
    description: str


class RunDetail(BaseModel):
    run_id: str
    state: ActionState
    created_at: float
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    elapsed_seconds: float = 0.0
    burst_detected: bool = False
    serverless_verified: bool = False
    recovery_started: bool = False
    baseline_verified: bool = False
    burst_canary: Optional[CalculationCanary] = None
    recovery_canary: Optional[CalculationCanary] = None
    error_message: Optional[str] = None
    logs: List[LogEntry] = Field(default_factory=list)


class DemoStatusResponse(BaseModel):
    state: ActionState
    active_run_id: Optional[str] = None
    can_burst: bool = True
    can_recover: bool = False
    current_run: Optional[RunDetail] = None
    last_completed_run: Optional[RunDetail] = None
    links_heading: str
    ordered_links: List[OrderedLink]


class BurstTriggerResponse(BaseModel):
    run_id: str
    status: ActionState
    message: str


class RecoverTriggerResponse(BaseModel):
    run_id: str
    status: ActionState
    message: str
