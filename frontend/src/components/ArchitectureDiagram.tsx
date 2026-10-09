import React from 'react';
import { ArrowRight, ArrowDownRight, ArrowUpRight, Cpu, Database, Server, Zap, Shield, Activity } from 'lucide-react';

export const ArchitectureDiagram: React.FC = () => {
  return (
    <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-5 shadow-xl">
      <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-5">
        <div>
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400" />
            Architecture Overview & Request Flow
          </h2>
          <p className="text-xs text-slate-400">
            Self-contained hybrid orchestration model deployed on Microsoft Azure
          </p>
        </div>
        <span className="text-[11px] font-mono tracking-wide px-2.5 py-1 rounded-md bg-slate-800 text-slate-400 border border-slate-700">
          Architecture Illustration (Not Live Telemetry)
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
        {/* Step 1: Ingress */}
        <div className="lg:col-span-3 bg-slate-850 p-4 rounded-lg border border-slate-750 text-center">
          <div className="text-[10px] uppercase font-mono tracking-wider text-slate-400 font-semibold mb-1">Entrypoint</div>
          <div className="font-medium text-sm text-white flex items-center justify-center gap-1.5 mb-2">
            <Server className="w-4 h-4 text-blue-400" />
            Azure Load Balancer
          </div>
          <div className="text-xs font-mono text-slate-400 bg-slate-900/90 py-1 px-2 rounded border border-slate-800 break-all">
            burstops-cloud-ga3cvf
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            Public NGINX Ingress proxies incoming HTTP traffic on port 80/443.
          </p>
        </div>

        {/* Arrow to Gateway */}
        <div className="hidden lg:flex lg:col-span-1 justify-center text-slate-600">
          <ArrowRight className="w-6 h-6 animate-pulse text-blue-500/70" />
        </div>

        {/* Step 2: Gateway */}
        <div className="lg:col-span-4 bg-gradient-to-b from-blue-950/40 to-slate-850 p-4 rounded-lg border border-blue-500/30 relative">
          <div className="absolute -top-2.5 right-3 bg-blue-500 text-slate-950 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
            Core Engine
          </div>
          <div className="text-[10px] uppercase font-mono tracking-wider text-blue-400 font-semibold mb-1">Layer-7 Gateway</div>
          <div className="font-semibold text-sm text-white flex items-center gap-1.5 mb-1">
            <Cpu className="w-4 h-4 text-cyan-400" />
            BurstOps Gateway (2 Replicas)
          </div>
          <div className="text-[11px] text-slate-300 space-y-1 my-2">
            <div className="flex items-center justify-between bg-slate-900/80 px-2 py-1 rounded border border-slate-800 text-[11px]">
              <span className="text-slate-400 font-mono">Hysteresis:</span>
              <span className="text-amber-400 font-semibold font-mono">80% Burst / 60% Recover</span>
            </div>
            <div className="flex items-center justify-between bg-slate-900/80 px-2 py-1 rounded border border-slate-800 text-[11px]">
              <span className="text-slate-400 font-mono">Controller:</span>
              <span className="text-cyan-400 font-semibold font-mono">PI Continuous Deflection</span>
            </div>
            <div className="flex items-center justify-between bg-slate-900/80 px-2 py-1 rounded border border-slate-800 text-[11px]">
              <span className="text-slate-400 font-mono">Backplane:</span>
              <span className="text-purple-400 font-semibold font-mono">Redis Distributed Lock</span>
            </div>
          </div>
          <p className="text-[11px] text-slate-400">
            PromQL poller queries in-cluster Prometheus every 2s for backend CPU usage.
          </p>
        </div>

        {/* Arrow to Dual Execution */}
        <div className="hidden lg:flex lg:col-span-1 flex-col justify-center items-center gap-8 text-slate-600">
          <ArrowUpRight className="w-5 h-5 text-emerald-500/70" />
          <ArrowDownRight className="w-5 h-5 text-purple-500/70" />
        </div>

        {/* Step 3: Dual Execution Targets */}
        <div className="lg:col-span-3 space-y-3">
          {/* Target A: Kubernetes */}
          <div className="bg-slate-850 p-3 rounded-lg border border-emerald-500/30">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-mono uppercase text-emerald-400 font-bold">Baseline Route (&lt; 80%)</span>
              <span className="text-[10px] text-slate-400 font-mono">Fixed Cost</span>
            </div>
            <div className="text-xs font-semibold text-white flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5 text-emerald-400" />
              AKS Pods (namespace: burstops)
            </div>
            <p className="text-[10px] text-slate-400 mt-1">
              Sieve calculation backend. Autoscales via HPA (2 to 8 replicas) on prolonged loads.
            </p>
          </div>

          {/* Target B: Azure Functions */}
          <div className="bg-slate-850 p-3 rounded-lg border border-purple-500/30">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-mono uppercase text-purple-400 font-bold">Burst Route (&ge; 80%)</span>
              <span className="text-[10px] text-slate-400 font-mono">Scale to Zero ($0 idle)</span>
            </div>
            <div className="text-xs font-semibold text-white flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-purple-400" />
              Azure Function (Flex Consumption)
            </div>
            <p className="text-[10px] text-slate-400 mt-1">
              Python 3.13 serverless target. Validates HMAC-SHA256 signature + Function Key.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
