import { CalculationCanary, GatewayHealth, ParsedGatewayMetrics } from '../types';
import { parsePrometheusMetrics } from './prometheusParser';

const DEFAULT_GATEWAY_BASE = '/gateway';
const DEFAULT_CPUSIM_BASE = '/cpu-sim';

export function getGatewayBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const custom = localStorage.getItem('burstops_gateway_url');
    if (custom && custom.trim().length > 0) {
      return custom.trim().replace(/\/+$/, '');
    }
  }
  return DEFAULT_GATEWAY_BASE;
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
