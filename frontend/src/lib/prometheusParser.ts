import { ParsedGatewayMetrics } from '../types';

/**
 * Parses Prometheus text exposition format into structured BurstOps gateway metrics.
 */
export function parsePrometheusMetrics(text: string): ParsedGatewayMetrics {
  const result: ParsedGatewayMetrics = {
    routingMode: 0,
    cpuObservedPercent: 0,
    cpuSetpointPercent: 70.0,
    deflectRatio: 0,
    requestsRoutedK8s: 0,
    requestsRoutedServerless: 0,
    upstreamLatencySeconds: 0.005,
    transitionsBurstStart: 0,
    transitionsRecoverBaseline: 0,
    breakevenOverflowRps: 28.55,
    costPerRequestK8sUsd: 0.000008,
    costPerRequestServerlessUsd: 0.000046,
    hpaLagCostUsdTotal: 0,
    isLeader: true,
    redisUp: true,
    timestamp: Date.now(),
  };

  if (!text || typeof text !== 'string') {
    return result;
  }

  const lines = text.split('\n');

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }

    // Match metric name and value, handling optional labels {key="value",...}
    const match = trimmed.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([+-]?(?:[0-9]*[.])?[0-9]+(?:[eE][+-]?[0-9]+)?)/);
    if (!match) {
      continue;
    }

    const [, metricName, labelStr, valueStr] = match;
    const value = parseFloat(valueStr);
    if (isNaN(value)) continue;

    // Parse labels
    const labels: Record<string, string> = {};
    if (labelStr) {
      const labelPairs = labelStr.split(',');
      for (const pair of labelPairs) {
        const [k, v] = pair.split('=');
        if (k && v) {
          labels[k.trim()] = v.trim().replace(/^"|"$/g, '');
        }
      }
    }

    switch (metricName) {
      case 'gateway_routing_mode':
        result.routingMode = Math.round(value);
        break;

      case 'gateway_cpu_observed_percent':
        result.cpuObservedPercent = Math.round(value * 10) / 10;
        break;

      case 'gateway_cpu_setpoint_percent':
        result.cpuSetpointPercent = value;
        break;

      case 'gateway_deflect_ratio':
        result.deflectRatio = Math.round(value * 1000) / 1000;
        break;

      case 'gateway_requests_routed_total':
        if (labels.route === 'serverless' || labels.route === 'azure_function') {
          result.requestsRoutedServerless = value;
        } else if (labels.route === 'k8s' || labels.route === 'baseline') {
          result.requestsRoutedK8s = value;
        } else {
          // If no specific route label, check direction or store
          result.requestsRoutedK8s = value;
        }
        break;

      case 'gateway_upstream_latency_seconds':
      case 'gateway_upstream_latency_seconds_sum':
        result.upstreamLatencySeconds = Math.round(value * 10000) / 10000;
        break;

      case 'gateway_state_transitions_total':
        if (labels.direction === 'burst_start' || labels.direction === 'burst') {
          result.transitionsBurstStart = value;
        } else if (labels.direction === 'recover_baseline' || labels.direction === 'baseline') {
          result.transitionsRecoverBaseline = value;
        }
        break;

      case 'gateway_breakeven_overflow_rps':
        result.breakevenOverflowRps = Math.round(value * 100) / 100;
        break;

      case 'gateway_cost_per_request_usd':
        if (labels.route === 'serverless') {
          result.costPerRequestServerlessUsd = value;
        } else if (labels.route === 'k8s') {
          result.costPerRequestK8sUsd = value;
        }
        break;

      case 'gateway_hpa_lag_cost_usd_total':
        result.hpaLagCostUsdTotal = Math.round(value * 10000) / 10000;
        break;

      case 'gateway_is_leader':
        result.isLeader = value === 1;
        break;

      case 'gateway_redis_up':
        result.redisUp = value === 1;
        break;
    }
  }

  return result;
}
