export type ActionState =
  | 'Ready'
  | 'Starting'
  | 'Running'
  | 'Burst detected'
  | 'Serverless deflection verified'
  | 'Recovery in progress'
  | 'Baseline verified'
  | 'Failed'
  | 'Timed out'
  | 'Cancelled';

export type LogLevel = 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS';

export interface LogEntry {
  timestamp: number;
  iso_time: string;
  level: LogLevel;
  message: string;
}

export interface CalculationCanary {
  source: string;
  impl: string;
  hostname?: string | null;
  instance_id?: string | null;
  prime_count: number;
  prime_sum: number;
  cold_start?: boolean | null;
  duration_ms?: number;
  timestamp?: number;
}

export interface OrderedLink {
  number: number;
  title: string;
  url: string;
  description: string;
}

export interface RunDetail {
  run_id: string;
  state: ActionState;
  created_at: number;
  started_at?: number | null;
  ended_at?: number | null;
  elapsed_seconds: number;
  burst_detected: boolean;
  serverless_verified: boolean;
  recovery_started: boolean;
  baseline_verified: boolean;
  burst_canary?: CalculationCanary | null;
  recovery_canary?: CalculationCanary | null;
  error_message?: string | null;
  logs: LogEntry[];
}

export interface DemoStatusResponse {
  state: ActionState;
  active_run_id?: string | null;
  can_burst: boolean;
  can_recover: boolean;
  current_run?: RunDetail | null;
  last_completed_run?: RunDetail | null;
  links_heading: string;
  ordered_links: OrderedLink[];
}

export interface GatewayHealth {
  status: string;
  mode?: string;
  routing_mode?: number;
  cpu_observed_percent?: number;
  deflect_ratio?: number;
  is_leader?: boolean;
  redis_up?: boolean;
  timestamp?: number;
}

export interface ParsedGatewayMetrics {
  routingMode: number; // 0 = baseline, 1 = burst
  cpuObservedPercent: number;
  cpuSetpointPercent: number;
  deflectRatio: number;
  requestsRoutedK8s: number;
  requestsRoutedServerless: number;
  upstreamLatencySeconds: number;
  transitionsBurstStart: number;
  transitionsRecoverBaseline: number;
  breakevenOverflowRps: number;
  costPerRequestK8sUsd: number;
  costPerRequestServerlessUsd: number;
  hpaLagCostUsdTotal: number;
  isLeader: boolean;
  redisUp: boolean;
  timestamp: number;
}

export interface MetricHistoryPoint {
  timestamp: number;
  timeLabel: string;
  cpuPercent: number;
  deflectRatio: number;
  k8sRps: number;
  serverlessRps: number;
  totalRps: number;
  latencyMs: number;
  routingMode: number;
}

export type PortalBlade =
  | 'home'
  | 'gateway'
  | 'metrics'
  | 'cost'
  | 'load-test'
  | 'activity-log'
  | 'service-health'
  | 'all-resources';

export type GatewaySubTab = 'overview' | 'monitoring' | 'properties' | 'capabilities';

export interface PortalNotification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: number;
  read?: boolean;
}

export interface ActivityLogItem {
  id: string;
  timestamp: string;
  operationName: string;
  status: 'Succeeded' | 'In Progress' | 'Failed' | 'Warning';
  initiatedBy: string;
  resource: string;
  cpuPercent?: number;
  details: string;
}
