import React from 'react';
import { ArrowRight, ArrowDownRight, ArrowUpRight, Cpu, Server, Zap, Activity } from 'lucide-react';

export const ArchitectureDiagram: React.FC = () => {
  return (
    <div className="azure-card bg-white dark:bg-[#1B1A19] border border-[#EDEBE9] dark:border-[#292827] rounded-sm p-5 shadow-xs">
      <div className="flex items-center justify-between pb-3 border-b border-[#EDEBE9] dark:border-[#292827] mb-4">
        <div>
          <h2 className="text-sm sm:text-base font-semibold text-[#323130] dark:text-white flex items-center gap-2">
            <Activity className="w-4 h-4 text-azure-500" />
            Architecture Overview & Request Flow
          </h2>
          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D]">
            Self-contained hybrid orchestration model deployed on Microsoft Azure Central India
          </p>
        </div>
        <span className="text-[11px] font-mono tracking-wide px-2.5 py-0.5 rounded-sm bg-[#FAF9F8] dark:bg-[#11100F] text-[#605E5C] dark:text-[#A19F9D] border border-[#EDEBE9] dark:border-[#292827]">
          Architecture Illustration
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
        {/* Step 1: Ingress */}
        <div className="lg:col-span-3 bg-[#FAF9F8] dark:bg-[#11100F] p-4 rounded-sm border border-[#EDEBE9] dark:border-[#292827] text-center">
          <div className="text-[10px] uppercase font-mono tracking-wider text-slate-500 dark:text-slate-400 font-semibold mb-1">
            Entrypoint
          </div>
          <div className="font-semibold text-xs sm:text-sm text-[#323130] dark:text-white flex items-center justify-center gap-1.5 mb-2">
            <Server className="w-4 h-4 text-azure-500" />
            Azure Load Balancer
          </div>
          <div className="text-xs font-mono text-azure-600 dark:text-azure-400 bg-white dark:bg-black/40 py-1 px-2 rounded-sm border border-[#EDEBE9] dark:border-[#292827] break-all">
            burstops-cloud-ga3cvf
          </div>
          <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] mt-2 leading-relaxed">
            Public NGINX Ingress proxies incoming HTTP traffic on port 80/443.
          </p>
        </div>

        {/* Arrow to Gateway */}
        <div className="hidden lg:flex lg:col-span-1 justify-center text-azure-500">
          <ArrowRight className="w-5 h-5 animate-pulse" />
        </div>

        {/* Step 2: Gateway */}
        <div className="lg:col-span-4 bg-azure-50/40 dark:bg-azure-950/20 p-4 rounded-sm border border-azure-300 dark:border-azure-800 relative">
          <div className="absolute -top-2.5 right-3 bg-azure-500 text-white text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider">
            Core Engine
          </div>
          <div className="text-[10px] uppercase font-mono tracking-wider text-azure-600 dark:text-azure-400 font-semibold mb-1">
            Layer-7 Gateway
          </div>
          <div className="font-semibold text-sm text-[#323130] dark:text-white flex items-center gap-1.5 mb-1">
            <Cpu className="w-4 h-4 text-azure-500" />
            BurstOps Gateway (2 Replicas)
          </div>
          <div className="text-[11px] text-[#323130] dark:text-[#F3F2F1] space-y-1 my-2">
            <div className="flex items-center justify-between bg-white dark:bg-[#1B1A19] px-2 py-1 rounded-sm border border-[#EDEBE9] dark:border-[#292827]">
              <span className="text-[#605E5C] dark:text-[#A19F9D]">Hysteresis:</span>
              <span className="text-amber-600 dark:text-amber-400 font-semibold font-mono">80% Burst / 60% Recover</span>
            </div>
            <div className="flex items-center justify-between bg-white dark:bg-[#1B1A19] px-2 py-1 rounded-sm border border-[#EDEBE9] dark:border-[#292827]">
              <span className="text-[#605E5C] dark:text-[#A19F9D]">Controller:</span>
              <span className="text-azure-600 dark:text-azure-400 font-semibold font-mono">PI Continuous Deflection</span>
            </div>
            <div className="flex items-center justify-between bg-white dark:bg-[#1B1A19] px-2 py-1 rounded-sm border border-[#EDEBE9] dark:border-[#292827]">
              <span className="text-[#605E5C] dark:text-[#A19F9D]">Backplane:</span>
              <span className="text-purple-600 dark:text-purple-400 font-semibold font-mono">Redis Distributed Lock</span>
            </div>
          </div>
          <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
            PromQL poller queries in-cluster Prometheus every 2s for backend CPU usage.
          </p>
        </div>

        {/* Arrow to Dual Execution */}
        <div className="hidden lg:flex lg:col-span-1 flex-col justify-center items-center gap-6">
          <ArrowUpRight className="w-5 h-5 text-emerald-500" />
          <ArrowDownRight className="w-5 h-5 text-purple-500" />
        </div>

        {/* Step 3: Dual Execution Targets */}
        <div className="lg:col-span-3 space-y-3">
          {/* Target A: Kubernetes */}
          <div className="bg-emerald-50/40 dark:bg-emerald-950/20 p-3 rounded-sm border border-emerald-300 dark:border-emerald-800">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-mono uppercase text-emerald-700 dark:text-emerald-300 font-bold">
                Baseline Route (&lt; 80%)
              </span>
              <span className="text-[10px] text-slate-500 font-mono">Fixed Cost</span>
            </div>
            <div className="text-xs font-semibold text-[#323130] dark:text-white flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5 text-emerald-600" />
              AKS Pods (namespace: burstops)
            </div>
            <p className="text-[10px] text-[#605E5C] dark:text-[#A19F9D] mt-1">
              Sieve calculation backend. Autoscales via HPA (2 to 8 replicas) on prolonged loads.
            </p>
          </div>

          {/* Target B: Azure Functions */}
          <div className="bg-purple-50/40 dark:bg-purple-950/20 p-3 rounded-sm border border-purple-300 dark:border-purple-800">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-mono uppercase text-purple-700 dark:text-purple-300 font-bold">
                Burst Route (≥ 80%)
              </span>
              <span className="text-[10px] text-slate-500 font-mono">Scale to Zero ($0 idle)</span>
            </div>
            <div className="text-xs font-semibold text-[#323130] dark:text-white flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-purple-600" />
              Azure Function (Flex Consumption)
            </div>
            <p className="text-[10px] text-[#605E5C] dark:text-[#A19F9D] mt-1">
              Python 3.13 serverless target. Validates HMAC-SHA256 signature + Function Key.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
