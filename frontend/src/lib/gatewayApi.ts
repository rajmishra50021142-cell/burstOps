import {
  CalculationCanary,
  DigitalTwinExecutionResult,
  DigitalTwinTaskPayload,
  GatewayHealth,
  GoldenTrioTelemetry,
  ParsedGatewayMetrics,
} from '../types';
import { parsePrometheusMetrics } from './prometheusParser';

// Dynamically resolves to current browser origin in production / mobile / Render
export const VITE_API_BASE_URL: string = (() => {
  const env = (import.meta as any)?.env;
  const envVal = env?.VITE_API_BASE_URL;
  if (envVal && typeof envVal === 'string' && envVal.trim().length > 0) {
    return envVal.trim().replace(/\/+$/, '');
  }
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin;
  }
  return '';
})();

const DEFAULT_CPUSIM_BASE = '/cpu-sim';

export function getGatewayBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const custom = localStorage.getItem('burstops_gateway_url');
    if (custom && custom.trim().length > 0) {
      // Clear any stale localhost configuration if accessed via remote Render URL or mobile
      const isRemote = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';
      if (isRemote && (custom.includes('localhost') || custom.includes('127.0.0.1'))) {
        localStorage.removeItem('burstops_gateway_url');
      } else {
        return custom.trim().replace(/\/+$/, '');
      }
    }
  }

  if (VITE_API_BASE_URL && VITE_API_BASE_URL.trim().length > 0) {
    return VITE_API_BASE_URL;
  }

  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin;
  }

  return '';
}

export function setGatewayBaseUrl(url: string): void {
  if (typeof window !== 'undefined') {
    if (!url || url.trim() === '') {
      localStorage.removeItem('burstops_gateway_url');
    } else {
      localStorage.setItem('burstops_gateway_url', url.trim());
    }
  }
}

/**
 * Fetches gateway health endpoint (GET /health).
 */
export async function fetchGatewayHealth(): Promise<GatewayHealth> {
  const base = getGatewayBaseUrl();
  const url = `${base}/health`;
  const resp = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!resp.ok) {
    throw new Error(`Gateway returned HTTP ${resp.status}`);
  }
  const data = await resp.json();
  return {
    status: data.status || 'healthy',
    mode: data.mode || (data.routing_mode === 1 ? 'burst' : 'baseline'),
    routing_mode: data.routing_mode ?? (data.mode === 'burst' ? 1 : 0),
    cpu_observed_percent: data.cpu_observed ?? data.cpu_observed_percent ?? 0,
    deflect_ratio: data.deflect_ratio ?? 0,
    is_leader: data.is_leader ?? true,
    redis_up: data.redis_up ?? true,
    timestamp: Date.now(),
  };
}

/**
 * Fetches and parses Prometheus metrics from gateway (GET /metrics).
 */
export async function fetchGatewayMetrics(): Promise<ParsedGatewayMetrics> {
  const base = getGatewayBaseUrl();
  const url = `${base}/metrics`;
  const resp = await fetch(url, { headers: { Accept: 'text/plain' } });
  if (!resp.ok) {
    throw new Error(`Failed to fetch gateway metrics: HTTP ${resp.status}`);
  }
  const text = await resp.text();
  return parsePrometheusMetrics(text);
}

/**
 * Sends a single test calculate request to the Gateway (GET /calculate).
 */
export async function sendTestCalculate(): Promise<CalculationCanary> {
  const base = getGatewayBaseUrl();
  const url = `${base}/calculate`;
  const start = performance.now();
  const resp = await fetch(url, { headers: { Accept: 'application/json' } });
  const duration = Math.round(performance.now() - start);

  if (!resp.ok) {
    throw new Error(`Calculate request failed: HTTP ${resp.status}`);
  }
  const data = await resp.json();
  return {
    source: data.source || 'unknown',
    impl: data.impl || 'sieve',
    hostname: data.hostname || null,
    instance_id: data.instance_id || null,
    prime_count: data.prime_count ?? 168,
    prime_sum: data.prime_sum ?? 76127,
    cold_start: data.cold_start ?? false,
    duration_ms: duration,
    timestamp: Date.now(),
  };
}

/**
 * Sets CPU simulation percentage on port 8002 (POST /set?pct=).
 */
export async function setCpuSimPct(pct: number): Promise<{ success: boolean; message: string }> {
  const url = `${DEFAULT_CPUSIM_BASE}/set?pct=${Math.round(pct)}`;
  try {
    const resp = await fetch(url, { method: 'POST' });
    if (!resp.ok) {
      return { success: false, message: `HTTP ${resp.status}` };
    }
    const data = await resp.json().catch(() => ({}));
    return { success: true, message: data.message || `Set CPU to ${pct}%` };
  } catch (err: any) {
    return { success: false, message: err.message || 'cpu-sim offline' };
  }
}

/**
 * Triggers ramp-up on cpu-sim (POST /ramp-up).
 */
export async function rampUpCpuSim(): Promise<{ success: boolean; message: string }> {
  const url = `${DEFAULT_CPUSIM_BASE}/ramp-up`;
  try {
    const resp = await fetch(url, { method: 'POST' });
    if (!resp.ok) {
      return { success: false, message: `HTTP ${resp.status}` };
    }
    const data = await resp.json().catch(() => ({}));
    return { success: true, message: data.message || 'Triggered CPU Ramp Up' };
  } catch (err: any) {
    return { success: false, message: err.message || 'cpu-sim offline' };
  }
}

/**
 * Triggers ramp-down on cpu-sim (POST /ramp-down).
 */
export async function rampDownCpuSim(): Promise<{ success: boolean; message: string }> {
  const url = `${DEFAULT_CPUSIM_BASE}/ramp-down`;
  try {
    const resp = await fetch(url, { method: 'POST' });
    if (!resp.ok) {
      return { success: false, message: `HTTP ${resp.status}` };
    }
    const data = await resp.json().catch(() => ({}));
    return { success: true, message: data.message || 'Triggered CPU Ramp Down' };
  } catch (err: any) {
    return { success: false, message: err.message || 'cpu-sim offline' };
  }
}

/**
 * Sends a real Digital Twin computation request to the Gateway or Backend.
 */
export async function sendDigitalTwinCompute(
  payload: DigitalTwinTaskPayload
): Promise<DigitalTwinExecutionResult> {
  const base = getGatewayBaseUrl();
  // Try /api/twin/compute on gateway, fallback to /calculate
  const url = `${base}/api/twin/compute`;
  const start = performance.now();

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    // If gateway base fails or rewrite is not active, try root /calculate
    resp = await fetch(`${base}/calculate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  const duration = Math.round(performance.now() - start);
  if (!resp.ok) {
    throw new Error(`Digital Twin execution failed: HTTP ${resp.status}`);
  }

  const data = await resp.json();
  const meta = data.gateway_metadata || {};

  return {
    id: `twin-res-${Math.random().toString(36).substring(2, 9)}`,
    timestamp: Date.now(),
    twin_id: data.twin_id || payload.twin_id,
    subsystem: data.subsystem || payload.subsystem,
    executed_by: data.executed_by || (data.source === 'serverless' ? 'AZURE_SERVERLESS_FUNCTION' : 'AKS_BASE_POD'),
    source: data.source || meta.route || 'k8s',
    impl: data.impl || 'burstops-digital-twin',
    node_hostname: data.node_hostname || data.hostname || data.instance_id || 'unknown',
    instance_id: data.instance_id,
    process_pid: data.process_pid,
    cpu_time_ms: data.cpu_time_ms ?? Math.round(duration * 0.9),
    wall_time_ms: data.wall_time_ms ?? duration,
    physics_output: data.physics_output || {
      verification_hash: data.verification_hash || 'hash-verified',
    },
    gamma_ratio: meta.gamma_ratio ?? data.gamma_ratio ?? 1.5,
    routing_reason: meta.routing_reason ?? data.routing_reason ?? 'BASELINE_K8S_NORMAL',
    dynamic_threshold_pct: meta.dynamic_threshold_pct,
    load_velocity_pct_per_s: meta.load_velocity_pct_per_s,
    composite_utilization_pct: meta.composite_utilization_pct,
    active_compute_slots: meta.active_compute_slots,
    prewarm_state: meta.prewarm_state,
    cold_start: data.cold_start ?? false,
  };
}

/**
 * Fetches real-time Golden Trio telemetry and capacity metrics.
 */
export async function fetchGoldenTrioTelemetry(): Promise<GoldenTrioTelemetry> {
  const base = getGatewayBaseUrl();
  const url = `${base}/api/golden-trio/status`;
  try {
    const resp = await fetch(url, { headers: { Accept: 'application/json' } });
    if (resp.ok) {
      return await resp.json();
    }
  } catch (e) {
    // Fallback to local /api/golden-trio/status
  }

  const localResp = await fetch('/api/golden-trio/status');
  if (!localResp.ok) {
    throw new Error(`Failed to fetch Golden Trio status: HTTP ${localResp.status}`);
  }
  return await localResp.json();
}

