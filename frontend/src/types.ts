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
