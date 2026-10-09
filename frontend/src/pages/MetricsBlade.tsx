import React, { useState } from 'react';
import {
  BarChart3,
  Filter,
  Clock,
  RefreshCw,
  SlidersHorizontal,
  Layers,
  ChevronDown,
} from 'lucide-react';
import { ParsedGatewayMetrics, MetricHistoryPoint } from '../types';
import { AzureChart } from '../components/AzureChart';

interface MetricsBladeProps {
  metrics: ParsedGatewayMetrics | null;
  history: MetricHistoryPoint[];
  onRefresh: () => void;
}

export const MetricsBlade: React.FC<MetricsBladeProps> = ({
  metrics,
  history,
  onRefresh,
}) => {
  const [timeRange, setTimeRange] = useState<'5m' | '15m' | '1h'>('5m');

  // Filter history according to timeRange if desired
  const filteredData = React.useMemo(() => {
    if (timeRange === '5m') return history.slice(-60);
    if (timeRange === '15m') return history.slice(-120);
    return history;
  }, [history, timeRange]);

  const timeLabel = timeRange === '5m' ? 'Last 5 min' : timeRange === '15m' ? 'Last 15 min' : 'Last 1 hour';

  // Calculate summary stats
  const cpuValues = history.map((h) => h.cpuPercent);
  const avgCpu = cpuValues.length > 0 ? (cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length).toFixed(1) : '0.0';
  const maxCpu = cpuValues.length > 0 ? Math.max(...cpuValues).toFixed(1) : '0.0';
  const minCpu = cpuValues.length > 0 ? Math.min(...cpuValues).toFixed(1) : '0.0';

  return (
    <div className="p-4 sm:p-6 space-y-5 max-w-7xl mx-auto select-none">
      {/* Azure Monitor Filter Toolbar */}
      <div className="azure-card p-3 rounded-sm flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          {/* Scope Selector */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-[#FAF9F8] dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827]">
            <span className="text-[#605E5C] dark:text-[#A19F9D]">Scope:</span>
            <span className="font-semibold text-azure-600 dark:text-azure-400">burstops-gateway</span>
          </div>

          {/* Metric Namespace */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-[#FAF9F8] dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827]">
            <span className="text-[#605E5C] dark:text-[#A19F9D]">Namespace:</span>
            <span className="font-medium text-[#323130] dark:text-white">gateway/telemetry</span>
          </div>

          {/* Aggregation */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-[#FAF9F8] dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827]">
            <span className="text-[#605E5C] dark:text-[#A19F9D]">Aggregation:</span>
            <span className="font-medium text-[#323130] dark:text-white">Average (2s polling)</span>
          </div>
        </div>

        {/* Time-Range Selector Buttons */}
        <div className="flex items-center gap-1 bg-[#FAF9F8] dark:bg-[#11100F] p-0.5 rounded-sm border border-[#EDEBE9] dark:border-[#292827]">
          <Clock className="w-3.5 h-3.5 text-slate-400 ml-1.5" />
          <button
            onClick={() => setTimeRange('5m')}
            className={`px-2 py-0.5 rounded-sm transition-colors text-xs ${
              timeRange === '5m'
                ? 'bg-azure-500 text-white font-semibold'
                : 'text-[#605E5C] dark:text-[#A19F9D] hover:text-[#323130] dark:hover:text-white'
            }`}
          >
            5m
          </button>
          <button
            onClick={() => setTimeRange('15m')}
            className={`px-2 py-0.5 rounded-sm transition-colors text-xs ${
              timeRange === '15m'
                ? 'bg-azure-500 text-white font-semibold'
                : 'text-[#605E5C] dark:text-[#A19F9D] hover:text-[#323130] dark:hover:text-white'
            }`}
          >
            15m
          </button>
          <button
            onClick={() => setTimeRange('1h')}
            className={`px-2 py-0.5 rounded-sm transition-colors text-xs ${
              timeRange === '1h'
                ? 'bg-azure-500 text-white font-semibold'
                : 'text-[#605E5C] dark:text-[#A19F9D] hover:text-[#323130] dark:hover:text-white'
            }`}
          >
            1h
          </button>
        </div>
      </div>

      {/* Grid of 4 Azure Monitor Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Chart 1: Observed CPU vs 80% / 60% Hysteresis */}
        <AzureChart
          title="CPU Observed vs Setpoints"
          subtitle="gateway_cpu_observed_percent"
          data={filteredData}
          series={[{ key: 'cpuPercent', label: 'Observed CPU', color: '#0078D4', unit: '%' }]}
          showHysteresisThresholds={true}
          height={210}
          timeRangeLabel={timeLabel}
        />

        {/* Chart 2: Continuous Deflection Ratio */}
        <AzureChart
          title="Continuous Deflect Ratio"
          subtitle="gateway_deflect_ratio (PI controller output)"
          data={filteredData}
          series={[{ key: 'deflectRatio', label: 'Deflect Ratio', color: '#881798' }]}
          minY={0}
          maxY={1.0}
          height={210}
          timeRangeLabel={timeLabel}
        />

        {/* Chart 3: Requests Routed by Upstream Target */}
        <AzureChart
          title="Routing Throughput by Target (Req/s)"
          subtitle="gateway_requests_routed_total"
          data={filteredData}
          series={[
            { key: 'k8sRps', label: 'Kubernetes Pods', color: '#107C10', unit: ' rps' },
            { key: 'serverlessRps', label: 'Azure Functions', color: '#B146C2', unit: ' rps' },
          ]}
          height={210}
          timeRangeLabel={timeLabel}
        />

        {/* Chart 4: Upstream Latency */}
        <AzureChart
          title="Upstream Roundtrip Latency (ms)"
          subtitle="gateway_upstream_latency_seconds"
          data={filteredData}
          series={[{ key: 'latencyMs', label: 'p95 Latency', color: '#D83B01', unit: ' ms' }]}
          height={210}
          timeRangeLabel={timeLabel}
        />
      </div>

      {/* Metrics Summary Table */}
      <div className="azure-card rounded-sm overflow-hidden">
        <div className="px-4 py-2.5 bg-[#FAF9F8] dark:bg-[#1B1A19] border-b border-[#EDEBE9] dark:border-[#292827] flex items-center justify-between">
          <span className="font-semibold text-xs text-[#323130] dark:text-white">
            Metric Telemetry Summary ({timeLabel})
          </span>
          <span className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
            Source: Prometheus In-Cluster Exporter (Port 9090)
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full azure-table">
            <thead>
              <tr>
                <th>Metric Name</th>
                <th>Current</th>
                <th>Avg</th>
                <th>Min</th>
                <th>Max</th>
                <th>Unit</th>
                <th>Hysteresis Bound</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="font-semibold font-mono text-azure-600 dark:text-azure-400">gateway_cpu_observed_percent</td>
                <td className="font-mono">{metrics?.cpuObservedPercent.toFixed(1) ?? '0.0'}%</td>
                <td className="font-mono">{avgCpu}%</td>
                <td className="font-mono">{minCpu}%</td>
                <td className="font-mono">{maxCpu}%</td>
                <td>Percent</td>
                <td><span className="text-amber-600 dark:text-amber-400 font-mono text-[11px]">80% Burst / 60% Recover</span></td>
              </tr>
              <tr>
                <td className="font-semibold font-mono text-azure-600 dark:text-azure-400">gateway_deflect_ratio</td>
                <td className="font-mono">{(metrics?.deflectRatio ?? 0).toFixed(3)}</td>
                <td className="font-mono">-</td>
                <td className="font-mono">0.000</td>
                <td className="font-mono">1.000</td>
                <td>Ratio [0..1]</td>
                <td><span className="text-purple-600 dark:text-purple-400 font-mono text-[11px]">Continuous PI Deflection</span></td>
              </tr>
              <tr>
                <td className="font-semibold font-mono text-azure-600 dark:text-azure-400">gateway_requests_routed_total[k8s]</td>
                <td className="font-mono">{metrics?.requestsRoutedK8s.toLocaleString() ?? '0'}</td>
                <td className="font-mono">-</td>
                <td className="font-mono">-</td>
                <td className="font-mono">-</td>
                <td>Requests</td>
                <td><span className="text-emerald-600 dark:text-emerald-400 font-mono text-[11px]">Steady Baseline</span></td>
              </tr>
              <tr>
                <td className="font-semibold font-mono text-azure-600 dark:text-azure-400">gateway_requests_routed_total[serverless]</td>
                <td className="font-mono">{metrics?.requestsRoutedServerless.toLocaleString() ?? '0'}</td>
                <td className="font-mono">-</td>
                <td className="font-mono">-</td>
                <td className="font-mono">-</td>
                <td>Requests</td>
                <td><span className="text-purple-600 dark:text-purple-400 font-mono text-[11px]">Surge Deflection</span></td>
              </tr>
              <tr>
                <td className="font-semibold font-mono text-azure-600 dark:text-azure-400">gateway_upstream_latency_seconds</td>
                <td className="font-mono">{Math.round((metrics?.upstreamLatencySeconds ?? 0.005) * 1000)} ms</td>
                <td className="font-mono">-</td>
                <td className="font-mono">2 ms</td>
                <td className="font-mono">45 ms</td>
                <td>Milliseconds</td>
                <td><span className="text-slate-500 font-mono text-[11px]">p95 SLA &lt; 100ms</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
