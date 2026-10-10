import React from 'react';
import {
  RefreshCw,
  Flame,
  RotateCcw,
  ExternalLink,
  Loader2,
  LayoutDashboard,
} from 'lucide-react';
import { DemoStatusResponse } from '../types';

interface AzureCommandBarProps {
  onRefresh: () => void;
  isRefreshing?: boolean;
  onTriggerBurst: () => Promise<void>;
  onTriggerRecover: () => Promise<void>;
  isActionLoading: boolean;
  demoStatus: DemoStatusResponse | null;
}

export const AzureCommandBar: React.FC<AzureCommandBarProps> = ({
  onRefresh,
  isRefreshing = false,
  onTriggerBurst,
  onTriggerRecover,
  isActionLoading,
  demoStatus,
}) => {
  const canBurst = Boolean(demoStatus?.can_burst && !isActionLoading);
  const canRecover = Boolean(demoStatus?.can_recover && !isActionLoading);

  // Grab active Grafana link (from cloud demo response or fallback to azure ingress)
  const grafanaLink =
    demoStatus?.ordered_links?.find((l) => l.number === 2)?.url ||
    'http://burstops-cloud-ga3cvf.centralindia.cloudapp.azure.com/grafana/';

  return (
    <div className="bg-[#FAF9F8] dark:bg-[#11100F] border-b border-[#EDEBE9] dark:border-[#292827] px-4 sm:px-6 py-1.5 flex items-center justify-between select-none">
      <div className="flex items-center gap-1 shrink-0 flex-wrap">
        {/* Refresh */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="azure-btn-command text-[#323130] dark:text-[#F3F2F1]"
          title="Refresh current data"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-azure-500 ${isRefreshing ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>

        {/* Separator */}
        <div className="w-[1px] h-4 bg-[#EDEBE9] dark:bg-[#292827] mx-1" />

        {/* Simulate Burst */}
        <button
          onClick={onTriggerBurst}
          disabled={!canBurst}
          className={`azure-btn-command ${
            canBurst
              ? 'text-amber-600 dark:text-amber-400 font-semibold hover:bg-amber-50 dark:hover:bg-amber-950/30'
              : 'opacity-40 cursor-not-allowed'
          }`}
          title="Simulate burst traffic through Azure gateway (drives CPU >= 80%)"
        >
          {isActionLoading && !canBurst ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-500" />
          ) : (
            <Flame className="w-3.5 h-3.5 text-amber-500" />
          )}
          <span>Simulate Burst</span>
        </button>

        {/* Recover to Baseline */}
        <button
          onClick={onTriggerRecover}
          disabled={!canRecover}
          className={`azure-btn-command ${
            canRecover
              ? 'text-emerald-600 dark:text-emerald-400 font-semibold hover:bg-emerald-50 dark:hover:bg-emerald-950/30'
              : 'opacity-40 cursor-not-allowed'
          }`}
          title="Cease load and verify controller cools below 60% recovery threshold"
        >
          {isActionLoading && canRecover ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-500" />
          ) : (
            <RotateCcw className="w-3.5 h-3.5 text-emerald-500" />
          )}
          <span>Recover Baseline</span>
        </button>

        {/* Separator */}
        <div className="w-[1px] h-4 bg-[#EDEBE9] dark:bg-[#292827] mx-1" />

        {/* Grafana Deep Link (Verified working) */}
        <a
          href={grafanaLink}
          target="_blank"
          rel="noopener noreferrer"
          className="azure-btn-command text-[#323130] dark:text-[#F3F2F1] hover:text-amber-600"
          title="Open Grafana Dashboard on Azure"
        >
          <LayoutDashboard className="w-3.5 h-3.5 text-amber-500" />
          <span>Grafana Dashboard</span>
          <ExternalLink className="w-3 h-3 text-slate-400 ml-0.5" />
        </a>
      </div>
    </div>
  );
};
