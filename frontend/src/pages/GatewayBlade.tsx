import React from 'react';
import { ParsedGatewayMetrics, DemoStatusResponse } from '../types';

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

  return (
    <div className="p-4 sm:p-6 space-y-5 max-w-7xl mx-auto select-none">
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
            <span className="text-[#605E5C] dark:text-[#A19F9D] block text-[11px]">Routing Mode:</span>
            <span
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold ${
                isBurst
                  ? 'bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-700'
                  : 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700'
              }`}
            >
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
    </div>
  );
};
