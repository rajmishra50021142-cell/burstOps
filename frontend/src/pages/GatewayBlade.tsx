import React, { useEffect, useState } from 'react';
import {
  ParsedGatewayMetrics,
  DemoStatusResponse,
  GoldenTrioTelemetry,
} from '../types';
import { fetchGoldenTrioTelemetry } from '../lib/gatewayApi';
import { Server, Activity, TrendingUp, Layers } from 'lucide-react';

interface GatewayBladeProps {
  metrics: ParsedGatewayMetrics | null;
  isOnline: boolean;
  demoStatus?: DemoStatusResponse | null;
}

export const GatewayBlade: React.FC<GatewayBladeProps> = ({
  metrics,
  isOnline,
}) => {
  const routingMode = metrics?.routingMode ?? 0;
  const isBurst = routingMode === 1;

  const [trioData, setTrioData] = useState<GoldenTrioTelemetry | null>(null);

  useEffect(() => {
    let active = true;
    const fetchTelemetry = async () => {
      try {
        const data = await fetchGoldenTrioTelemetry();
        if (active) {
          setTrioData(data);
        }
      } catch {
        // Fallback gracefully
      }
    };
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 3000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const activeSlots = trioData?.capacity_model.active_compute_slots ?? (isBurst ? 8 : 2);
  const maxSlots = trioData?.capacity_model.aks_base_capacity_slots ?? 10;
  const compositeU = trioData?.capacity_model.composite_utilization_pct ?? (metrics?.cpuObservedPercent ?? 20.0);
  const thetaPct = trioData?.novelty_1_aimd_threshold.current_threshold_pct ?? 80.0;
  const p95Latency = trioData?.novelty_1_aimd_threshold.aks_p95_latency_ms ?? 450.0;
  const velocity = trioData?.novelty_2_predictive_prewarm.load_velocity_pct_per_s ?? 0.0;
  const prewarmState = trioData?.novelty_2_predictive_prewarm.prewarm_state ?? 'IDLE';

  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-7xl mx-auto select-none">
      {/* Essentials Panel */}
      <div className="azure-card bg-white dark:bg-[#1B1A19] border border-[#EDEBE9] dark:border-[#292827] rounded-sm overflow-hidden shadow-xs">
        <div className="px-4 py-2.5 bg-[#FAF9F8] dark:bg-[#11100F] border-b border-[#EDEBE9] dark:border-[#292827] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-xs text-[#323130] dark:text-white">Essentials</span>
            <span className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
              — Layer-7 Ingress Routing Engine
            </span>
          </div>
        </div>

        <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
          <div className="space-y-1">
            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px]">Resource group:</span>
            <span className="font-medium text-azure-600 dark:text-azure-400">
              rg-burstops-prod
            </span>

            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Status:</span>
            <div className="flex items-center gap-1.5 font-medium">
              <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-500' : 'bg-rose-500'}`} />
              <span>{isOnline ? 'Running (Active)' : 'Offline / Standby'}</span>
            </div>

            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Location:</span>
            <span className="font-medium text-[#323130] dark:text-white">Central India (centralindia)</span>
          </div>

          <div className="space-y-1">
            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px]">Subscription:</span>
            <span className="font-medium text-azure-600 dark:text-azure-400">
              Azure Subscription 1
            </span>

            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Subscription ID:</span>
            <span className="font-mono text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
              980e5d74-260c-49bc-ba07-2343e710859d
            </span>

            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Leader Replica:</span>
            <span className="font-mono text-[11px] text-[#323130] dark:text-white">
              {metrics?.isLeader ? 'burstops-gateway-0 (Leader)' : 'burstops-gateway-1 (Follower)'}
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px]">Dynamic Routing Mode:</span>
            <span
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold ${
                isBurst
                  ? 'bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-700'
                  : 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700'
              }`}
            >
              {isBurst ? `Burst Active (≥ ${thetaPct.toFixed(1)}%)` : `Baseline Steady (< ${thetaPct.toFixed(1)}%)`}
            </span>

            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Self-Tuning Threshold:</span>
            <span className="font-mono text-[11px] text-[#323130] dark:text-white">
              AIMD θ(t): <strong>{thetaPct.toFixed(1)}%</strong> | Recover: <strong>60.0%</strong>
            </span>

            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Backplane Lock:</span>
            <span className="text-[#323130] dark:text-white flex items-center gap-1">
              <span className={`w-1.5 h-1.5 rounded-full ${metrics?.redisUp ? 'bg-emerald-500' : 'bg-rose-500'}`} />
              Redis Distributed Sync
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px]">Upstream Baseline (K8s):</span>
            <span className="font-mono text-[11px] text-emerald-600 dark:text-emerald-400 truncate block">
              http://dummy-backend:8000
            </span>

            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Upstream Serverless:</span>
            <span className="font-mono text-[11px] text-purple-600 dark:text-purple-400 truncate block">
              https://func-burstops-cloud-ga3cvf...
            </span>

            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Auth Verification:</span>
            <span className="text-slate-500 font-mono text-[11px]">
              HMAC-SHA256 Signed
            </span>
          </div>
        </div>
      </div>

      {/* Explicit Capacity Model Card */}
      <div className="azure-card bg-white dark:bg-[#1B1A19] border border-[#EDEBE9] dark:border-[#292827] rounded-sm p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-[#EDEBE9] dark:border-[#292827]">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-emerald-500" />
            <h3 className="text-sm font-semibold text-[#323130] dark:text-white">
              Base AKS Pod Capacity Architecture (&quot;80% of What?&quot;)
            </h3>
          </div>
          <span className="font-mono text-xs px-2.5 py-1 rounded bg-[#FAF9F8] dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827] text-azure-600 dark:text-azure-400 font-bold">
            {activeSlots} / {maxSlots} Active Slots ({compositeU.toFixed(1)}% Load)
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-3 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm border border-[#EDEBE9] dark:border-[#292827] space-y-1">
            <div className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">Pod Resource Envelopes</div>
            <div className="font-mono font-semibold text-[#323130] dark:text-white">
              Requests: 250m CPU / 256Mi RAM
            </div>
            <div className="font-mono font-semibold text-[#323130] dark:text-white">
              Limits: 500m CPU (0.5 vCPU) / 512Mi RAM
            </div>
          </div>

          <div className="p-3 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm border border-[#EDEBE9] dark:border-[#292827] space-y-1">
            <div className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">Compute Concurrency Slots</div>
            <div className="font-mono font-semibold text-[#323130] dark:text-white">
              MAX_BASE_COMPUTE_SLOTS = 10
            </div>
            <div className="text-[11px] text-slate-500">
              100% Capacity = 10 concurrent heavy tasks.
            </div>
          </div>

          <div className="p-3 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm border border-[#EDEBE9] dark:border-[#292827] space-y-1">
            <div className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">Composite Utilization Formula</div>
            <div className="font-mono font-semibold text-azure-600 dark:text-azure-400">
              U = max(slots/10, cpu_ratio)
            </div>
            <div className="text-[11px] text-slate-500">
              Threshold = exactly 8 slots or 400m vCPU.
            </div>
          </div>
        </div>
      </div>

      {/* The Golden Trio Research Mechanisms */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Mechanism 1 */}
        <div className="azure-card bg-white dark:bg-[#1B1A19] border border-[#EDEBE9] dark:border-[#292827] rounded-sm p-4 shadow-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#323130] dark:text-white flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-azure-500" />
              Mechanism 1: Self-Tuning AIMD θ(t)
            </span>
            <span className="font-mono text-xs font-bold text-azure-600 dark:text-azure-400">
              {thetaPct.toFixed(1)}%
            </span>
          </div>
          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D]">
            Continuously monitors AKS p95 latency (now {p95Latency.toFixed(0)}ms) against 650ms target. Lowers threshold if latency spikes, raises threshold to save cost when healthy.
          </p>
        </div>

        {/* Mechanism 2 */}
        <div className="azure-card bg-white dark:bg-[#1B1A19] border border-[#EDEBE9] dark:border-[#292827] rounded-sm p-4 shadow-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#323130] dark:text-white flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-amber-500" />
              Mechanism 2: Pre-Warming (dU/dt)
            </span>
            <span className="font-mono text-xs font-bold text-amber-600 dark:text-amber-400">
              {prewarmState}
            </span>
          </div>
          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D]">
            Measures load velocity ({velocity >= 0 ? `+${velocity.toFixed(1)}` : velocity.toFixed(1)}%/s). Speculatively pre-warms Azure Functions before threshold breach to eliminate cold starts.
          </p>
        </div>

        {/* Mechanism 3 */}
        <div className="azure-card bg-white dark:bg-[#1B1A19] border border-[#EDEBE9] dark:border-[#292827] rounded-sm p-4 shadow-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#323130] dark:text-white flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-purple-500" />
              Mechanism 3: Semantic Router γ
            </span>
            <span className="font-mono text-xs font-bold text-purple-600 dark:text-purple-400">
              γ ≥ 1.50
            </span>
          </div>
          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D]">
            Evaluates compute-to-communication ratio. Pins light sensor checks to AKS; defers heavy Monte Carlo and FFT harmonics to Azure Serverless.
          </p>
        </div>
      </div>
    </div>
  );
};

