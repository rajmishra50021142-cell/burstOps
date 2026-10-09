import React, { useState } from 'react';
import {
  Cpu,
  ChevronDown,
  ChevronUp,
  Activity,
  Server,
  Zap,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Layers,
  Database,
  ExternalLink,
  Flame,
  RotateCcw,
  BarChart3,
  Globe,
  Settings2,
} from 'lucide-react';
import { ParsedGatewayMetrics, GatewaySubTab, MetricHistoryPoint, DemoStatusResponse } from '../types';
import { ArchitectureDiagram } from '../components/ArchitectureDiagram';
import { AzureChart } from '../components/AzureChart';
import { ResourceLinks } from '../components/ResourceLinks';

interface GatewayBladeProps {
  metrics: ParsedGatewayMetrics | null;
  history: MetricHistoryPoint[];
  isOnline: boolean;
  demoStatus: DemoStatusResponse | null;
  onNavigateToMetrics: () => void;
  onNavigateToLoadTest: () => void;
}

export const GatewayBlade: React.FC<GatewayBladeProps> = ({
  metrics,
  history,
  isOnline,
  demoStatus,
  onNavigateToMetrics,
  onNavigateToLoadTest,
}) => {
  const [isEssentialsExpanded, setIsEssentialsExpanded] = useState(true);
  const [activeTab, setActiveTab] = useState<GatewaySubTab>('overview');

  const cpuObserved = metrics?.cpuObservedPercent ?? 0;
  const routingMode = metrics?.routingMode ?? 0;
  const deflectRatio = metrics?.deflectRatio ?? 0;
  const latencyMs = Math.round((metrics?.upstreamLatencySeconds ?? 0.005) * 1000);
  const isBurst = routingMode === 1;

  // Recent data slice for preview
  const recentHistory = history.slice(-30);

  return (
    <div className="p-4 sm:p-6 space-y-5 max-w-7xl mx-auto select-none">
      {/* Essentials Collapsible Panel */}
      <div className="azure-card rounded-sm overflow-hidden">
        <div
          onClick={() => setIsEssentialsExpanded(!isEssentialsExpanded)}
          className="px-4 py-2.5 bg-[#FAF9F8] dark:bg-[#1B1A19] border-b border-[#EDEBE9] dark:border-[#292827] flex items-center justify-between cursor-pointer hover:bg-[#F3F2F1] dark:hover:bg-[#252423] transition-colors"
        >
          <div className="flex items-center gap-2">
            <span className="font-semibold text-xs text-[#323130] dark:text-white">Essentials</span>
            <span className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
              — Layer-7 Ingress Routing Engine
            </span>
          </div>
          <button className="text-slate-400 hover:text-slate-600 dark:hover:text-white">
            {isEssentialsExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>

        {isEssentialsExpanded && (
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            <div className="space-y-1">
              <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px]">Resource group:</span>
              <span className="font-medium text-azure-600 dark:text-azure-400 hover:underline cursor-pointer">
                rg-burstops-centralindia
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
              <span className="font-medium text-azure-600 dark:text-azure-400 hover:underline cursor-pointer">
                Azure Student / Enterprise
              </span>

              <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Subscription ID:</span>
              <span className="font-mono text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
                d86f7b12-92a1-4ce8-b50f-burstops001
              </span>

              <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Leader Replica:</span>
              <span className="font-mono text-[11px] text-[#323130] dark:text-white">
                {metrics?.isLeader ? 'burstops-gateway-0 (Leader)' : 'burstops-gateway-1 (Follower)'}
              </span>
            </div>

            <div className="space-y-1">
              <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px]">Routing Mode:</span>
              <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold ${
                isBurst
                  ? 'bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-700'
                  : 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700'
              }`}>
                {isBurst ? 'Burst Active (≥ 80%)' : 'Baseline Steady (< 80%)'}
              </span>

              <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Hysteresis Thresholds:</span>
              <span className="font-mono text-[11px] text-[#323130] dark:text-white">
                Burst: <strong>80%</strong> | Recover: <strong>60%</strong>
              </span>

              <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Backplane Lock:</span>
              <span className="text-[#323130] dark:text-white flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${metrics?.redisUp ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                Redis Distributed Sync
              </span>
            </div>

            <div className="space-y-1">
              <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px]">Upstream Baseline (K8s):</span>
              <span className="font-mono text-[11px] text-emerald-600 dark:text-emerald-400 truncate block" title="http://dummy-backend:8000">
                http://dummy-backend:8000
              </span>

              <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Upstream Serverless:</span>
              <span className="font-mono text-[11px] text-purple-600 dark:text-purple-400 truncate block" title="func-burstops-cvkzqc.azurewebsites.net">
                https://func-burstops-cvkzqc...
              </span>

              <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px] pt-2">Auth Verification:</span>
              <span className="text-slate-500 font-mono text-[11px]">
                HMAC-SHA256 Signed
              </span>
            </div>
          </div>
        )}
      </div>

      {/* 4 Azure KPI Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {/* KPI 1: Observed CPU */}
        <div className="azure-card p-4 rounded-sm space-y-1">
          <div className="flex items-center justify-between text-[#605E5C] dark:text-[#A19F9D] text-xs">
            <span>Observed CPU</span>
            <Cpu className="w-4 h-4 text-azure-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-[#323130] dark:text-white font-mono">
              {cpuObserved.toFixed(1)}%
            </span>
            <span className={`text-[11px] font-semibold px-1.5 py-0.2 rounded ${
              cpuObserved >= 80 ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300' :
              cpuObserved >= 60 ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300' :
              'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
            }`}>
              {cpuObserved >= 80 ? 'Surge (≥ 80%)' : cpuObserved >= 60 ? 'Hysteresis Band' : 'Normal'}
            </span>
          </div>
          <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] pt-1">
            Polled via PromQL from Prometheus every 2s
          </p>
        </div>

        {/* KPI 2: Routing State */}
        <div className="azure-card p-4 rounded-sm space-y-1">
          <div className="flex items-center justify-between text-[#605E5C] dark:text-[#A19F9D] text-xs">
            <span>Routing State</span>
            <Activity className="w-4 h-4 text-purple-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className={`text-2xl font-bold font-mono ${isBurst ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
              {isBurst ? 'Burst (1)' : 'Baseline (0)'}
            </span>
          </div>
          <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] pt-1">
            {isBurst ? 'Surplus requests deflected to Azure Function' : '100% requests served by Kubernetes pods'}
          </p>
        </div>

        {/* KPI 3: Continuous Deflection Ratio */}
        <div className="azure-card p-4 rounded-sm space-y-1">
          <div className="flex items-center justify-between text-[#605E5C] dark:text-[#A19F9D] text-xs">
            <span>Deflection Ratio</span>
            <Zap className="w-4 h-4 text-cyan-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-[#323130] dark:text-white font-mono">
              {(deflectRatio * 100).toFixed(1)}%
            </span>
            <span className="text-xs text-[#605E5C] dark:text-[#A19F9D] font-mono">
              ({deflectRatio.toFixed(3)})
            </span>
          </div>
          <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] pt-1">
            PI continuous controller smoothly dampens overflow
          </p>
        </div>

        {/* KPI 4: Upstream Latency */}
        <div className="azure-card p-4 rounded-sm space-y-1">
          <div className="flex items-center justify-between text-[#605E5C] dark:text-[#A19F9D] text-xs">
            <span>Upstream Latency (p95)</span>
            <Clock className="w-4 h-4 text-amber-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-[#323130] dark:text-white font-mono">
              {latencyMs} ms
            </span>
            <span className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold">
              Healthy
            </span>
          </div>
          <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] pt-1">
            End-to-end roundtrip including Sieve prime computation
          </p>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="border-b border-[#EDEBE9] dark:border-[#292827] flex items-center gap-6 text-xs font-semibold">
        <button
          onClick={() => setActiveTab('overview')}
          className={`pb-2.5 transition-colors relative ${
            activeTab === 'overview'
              ? 'text-azure-600 dark:text-azure-400 border-b-2 border-azure-500'
              : 'text-[#605E5C] dark:text-[#A19F9D] hover:text-[#323130] dark:hover:text-white'
          }`}
        >
          Overview & Architecture
        </button>

        <button
          onClick={() => setActiveTab('monitoring')}
          className={`pb-2.5 transition-colors relative ${
            activeTab === 'monitoring'
              ? 'text-azure-600 dark:text-azure-400 border-b-2 border-azure-500'
              : 'text-[#605E5C] dark:text-[#A19F9D] hover:text-[#323130] dark:hover:text-white'
          }`}
        >
          Monitoring (Telemetry Preview)
        </button>

        <button
          onClick={() => setActiveTab('properties')}
          className={`pb-2.5 transition-colors relative ${
            activeTab === 'properties'
              ? 'text-azure-600 dark:text-azure-400 border-b-2 border-azure-500'
              : 'text-[#605E5C] dark:text-[#A19F9D] hover:text-[#323130] dark:hover:text-white'
          }`}
        >
          Properties & Configuration
        </button>

        <button
          onClick={() => setActiveTab('capabilities')}
          className={`pb-2.5 transition-colors relative ${
            activeTab === 'capabilities'
              ? 'text-azure-600 dark:text-azure-400 border-b-2 border-azure-500'
              : 'text-[#605E5C] dark:text-[#A19F9D] hover:text-[#323130] dark:hover:text-white'
          }`}
        >
          Capabilities & Specs
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <ArchitectureDiagram />

          {demoStatus?.ordered_links && demoStatus.ordered_links.length > 0 && (
            <ResourceLinks heading={demoStatus.links_heading} links={demoStatus.ordered_links} />
          )}
        </div>
      )}

      {activeTab === 'monitoring' && (
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-xs text-[#323130] dark:text-white flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-azure-500" />
              Live Telemetry Streams (Last 5 Minutes)
            </h3>
            <button onClick={onNavigateToMetrics} className="text-xs text-azure-600 dark:text-azure-400 hover:underline">
              Open Full Metrics Explorer →
            </button>
          </div>

          <AzureChart
            title="CPU Observed vs Hysteresis Thresholds"
            subtitle="gateway_cpu_observed_percent"
            data={recentHistory}
            series={[{ key: 'cpuPercent', label: 'CPU Observed', color: '#0078D4', unit: '%' }]}
            showHysteresisThresholds={true}
            height={220}
          />

          <AzureChart
            title="Continuous Deflection Ratio"
            subtitle="gateway_deflect_ratio (0.0 to 1.0)"
            data={recentHistory}
            series={[{ key: 'deflectRatio', label: 'Deflect Ratio', color: '#881798' }]}
            minY={0}
            maxY={1.0}
            height={180}
          />
        </div>
      )}

      {activeTab === 'properties' && (
        <div className="azure-card p-5 rounded-sm space-y-4">
          <h3 className="font-semibold text-xs text-[#323130] dark:text-white flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-azure-500" />
            Gateway Instance Properties
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="p-3 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm space-y-2">
              <span className="font-semibold text-slate-500 text-[11px]">Network & Ingress</span>
              <div className="flex justify-between border-b border-[#EDEBE9] dark:border-[#292827] pb-1">
                <span>Listening Port:</span>
                <span className="font-mono">8000</span>
              </div>
              <div className="flex justify-between border-b border-[#EDEBE9] dark:border-[#292827] pb-1">
                <span>Prometheus Metrics Route:</span>
                <span className="font-mono">GET /metrics</span>
              </div>
              <div className="flex justify-between border-b border-[#EDEBE9] dark:border-[#292827] pb-1">
                <span>Health Probe Route:</span>
                <span className="font-mono">GET /health</span>
              </div>
              <div className="flex justify-between">
                <span>Sieve Work Canary Route:</span>
                <span className="font-mono">GET /calculate</span>
              </div>
            </div>

            <div className="p-3 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm space-y-2">
              <span className="font-semibold text-slate-500 text-[11px]">Control Loop Parameters</span>
              <div className="flex justify-between border-b border-[#EDEBE9] dark:border-[#292827] pb-1">
                <span>Burst Threshold:</span>
                <span className="font-mono text-amber-500 font-semibold">≥ 80.0% CPU</span>
              </div>
              <div className="flex justify-between border-b border-[#EDEBE9] dark:border-[#292827] pb-1">
                <span>Recovery Threshold:</span>
                <span className="font-mono text-emerald-500 font-semibold">&lt; 60.0% CPU</span>
              </div>
              <div className="flex justify-between border-b border-[#EDEBE9] dark:border-[#292827] pb-1">
                <span>Dead Band Hysteresis:</span>
                <span className="font-mono">20% (Prevents flapping)</span>
              </div>
              <div className="flex justify-between">
                <span>PromQL Sample Interval:</span>
                <span className="font-mono">2.0 seconds</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'capabilities' && (
        <div className="azure-card p-5 rounded-sm space-y-4">
          <h3 className="font-semibold text-xs text-[#323130] dark:text-white flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-azure-500" />
            BurstOps Architectural Capabilities
          </h3>

          <div className="space-y-3 text-xs leading-relaxed text-[#605E5C] dark:text-[#A19F9D]">
            <div className="p-3 bg-azure-50 dark:bg-azure-950/30 rounded-sm border border-azure-200 dark:border-azure-900/40">
              <h4 className="font-semibold text-azure-700 dark:text-azure-300 mb-1">
                1. Dual Upstream Execution Parity
              </h4>
              <p>
                Both upstream targets execute an identical cryptographic workload: Sieve of Eratosthenes across 2..1000, finding exactly 168 primes with a deterministic sum of 76,127. Neither client nor data integrity is compromised during deflection.
              </p>
            </div>

            <div className="p-3 bg-purple-50 dark:bg-purple-950/30 rounded-sm border border-purple-200 dark:border-purple-900/40">
              <h4 className="font-semibold text-purple-700 dark:text-purple-300 mb-1">
                2. Continuous PI Deflection vs Binary Switching
              </h4>
              <p>
                Rather than dumping 100% of traffic onto serverless immediately, the gateway uses a Proportional-Integral (PI) controller to compute a smooth continuous ratio (0.0 to 1.0). Only the necessary surplus is deflected, preserving Kubernetes capacity.
              </p>
            </div>

            <div className="p-3 bg-emerald-50 dark:bg-emerald-950/30 rounded-sm border border-emerald-200 dark:border-emerald-900/40">
              <h4 className="font-semibold text-emerald-700 dark:text-emerald-300 mb-1">
                3. High-Availability Distributed Leader Backplane
              </h4>
              <p>
                When multiple gateway replicas run in AKS, Redis distributed locking ensures only one leader polls Prometheus and executes the PI controller loop, synchronizing the deflection ratio across all worker replicas seamlessly.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
