import React from 'react';
import {
  DollarSign,
  TrendingDown,
  Scale,
  ShieldCheck,
  Zap,
  Server,
  ArrowRight,
  Info,
  Clock,
  PieChart,
} from 'lucide-react';
import { ParsedGatewayMetrics } from '../types';

interface CostBladeProps {
  metrics: ParsedGatewayMetrics | null;
}

export const CostBlade: React.FC<CostBladeProps> = ({ metrics }) => {
  const k8sCost = metrics?.costPerRequestK8sUsd ?? 0.000008;
  const slsCost = metrics?.costPerRequestServerlessUsd ?? 0.000046;
  const breakevenRps = metrics?.breakevenOverflowRps ?? 28.55;
  const hpaLagCost = metrics?.hpaLagCostUsdTotal ?? 0.0;
  const costMultiple = (slsCost / (k8sCost || 0.000001)).toFixed(2);

  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-7xl mx-auto select-none">
      {/* FinOps Header Banner */}
      <div className="azure-card p-5 rounded-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-5 h-5 text-emerald-500" />
            <h2 className="text-base font-semibold text-[#323130] dark:text-white">
              BurstOps FinOps & Cost Optimization Analysis
            </h2>
          </div>
          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D] max-w-2xl leading-relaxed">
            Comparing continuous baseline container economics (AKS) against on-demand ephemeral serverless deflection (Azure Functions Flex Consumption).
          </p>
        </div>

        <div className="flex items-center gap-2 self-start md:self-auto">
          <span className="px-3 py-1 rounded-sm bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-semibold text-xs border border-emerald-200 dark:border-emerald-800 flex items-center gap-1.5">
            <TrendingDown className="w-3.5 h-3.5" />
            FinOps Optimal Model
          </span>
        </div>
      </div>

      {/* 4 Azure Cost Analysis Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Kubernetes Baseline Cost */}
        <div className="azure-card p-4 rounded-sm space-y-2">
          <div className="flex items-center justify-between text-xs text-[#605E5C] dark:text-[#A19F9D]">
            <span>Kubernetes Baseline Cost</span>
            <Server className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-xl font-bold font-mono text-[#323130] dark:text-white">
            ${k8sCost.toFixed(6)}
          </div>
          <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
            Cost per request (amortized node pool cost across continuous baseline requests).
          </p>
        </div>

        {/* Card 2: Azure Function Serverless Cost */}
        <div className="azure-card p-4 rounded-sm space-y-2">
          <div className="flex items-center justify-between text-xs text-[#605E5C] dark:text-[#A19F9D]">
            <span>Serverless Burst Cost</span>
            <Zap className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-xl font-bold font-mono text-[#323130] dark:text-white">
            ${slsCost.toFixed(6)}
          </div>
          <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
            Cost per request on Azure Functions. Scales to zero during non-burst idle periods ($0 idle).
          </p>
        </div>

        {/* Card 3: Serverless Cost Premium */}
        <div className="azure-card p-4 rounded-sm space-y-2">
          <div className="flex items-center justify-between text-xs text-[#605E5C] dark:text-[#A19F9D]">
            <span>Cost Premium Multiple</span>
            <Scale className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-xl font-bold font-mono text-amber-600 dark:text-amber-400">
            {costMultiple}x
          </div>
          <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
            Serverless is ~{costMultiple}x more expensive per request than steady AKS, justifying hybrid baseline routing.
          </p>
        </div>

        {/* Card 4: Breakeven Overflow RPS */}
        <div className="azure-card p-4 rounded-sm space-y-2">
          <div className="flex items-center justify-between text-xs text-[#605E5C] dark:text-[#A19F9D]">
            <span>Breakeven Overflow RPS</span>
            <PieChart className="w-4 h-4 text-azure-500" />
          </div>
          <div className="text-xl font-bold font-mono text-azure-600 dark:text-azure-400">
            {breakevenRps.toFixed(2)} RPS
          </div>
          <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
            Below 28.55 RPS overflow, deflecting to serverless is strictly cheaper than keeping an extra VM node running 24/7.
          </p>
        </div>
      </div>

      {/* Deep-Dive Economic Explanation */}
      <div className="azure-card p-5 rounded-sm space-y-4">
        <h3 className="font-semibold text-xs text-[#323130] dark:text-white flex items-center gap-2">
          <Info className="w-4 h-4 text-azure-500" />
          The Economics of Hybrid Serverless Burst Deflection
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs leading-relaxed text-[#605E5C] dark:text-[#A19F9D]">
          <div className="space-y-3">
            <h4 className="font-semibold text-[#323130] dark:text-white flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center text-[11px]">
                1
              </span>
              Why Not 100% Serverless?
            </h4>
            <p>
              At high, continuous throughput, serverless functions incur a <strong>~5.76x cost premium</strong> per request compared to dedicated container instances. Running an entire continuous 24/7 production workload on Azure Functions would inflate monthly cloud expenditure dramatically.
            </p>
            <p>
              Kubernetes nodes provide rock-bottom marginal cost ($0.000008 / req) for continuous baseline loads.
            </p>
          </div>

          <div className="space-y-3">
            <h4 className="font-semibold text-[#323130] dark:text-white flex items-center gap-1.5">
              <span className="w-5 h-5 rounded-full bg-azure-100 dark:bg-azure-950 text-azure-600 dark:text-azure-400 flex items-center justify-center text-[11px]">
                2
              </span>
              Why Not 100% Kubernetes Overprovisioning?
            </h4>
            <p>
              Kubernetes Horizontal Pod Autoscalers (HPA) and Cluster Autoscaler suffer from an unavoidable <strong>3 to 7 minute provisioning lag</strong> when new VM nodes must be allocated and container images pulled.
            </p>
            <p>
              To survive unexpected traffic spikes without dropping requests, teams traditionally overprovision idle VM nodes, wasting thousands of dollars monthly. BurstOps deflections bridge the HPA lag safely with instantaneous serverless scale-to-zero.
            </p>
          </div>
        </div>
      </div>

      {/* Breakeven Threshold Visualizer */}
      <div className="azure-card p-5 rounded-sm space-y-3">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-[#323130] dark:text-white">
            Breakeven Boundary: 28.55 Continuous Overflow Requests/sec
          </span>
          <span className="font-mono text-azure-600 dark:text-azure-400 font-semibold">
            {breakevenRps} RPS
          </span>
        </div>

        {/* Visual Gauge Bar */}
        <div className="h-4 bg-slate-200 dark:bg-black/40 rounded-sm overflow-hidden flex text-[10px] text-white font-semibold">
          <div
            className="bg-emerald-500 flex items-center justify-center transition-all"
            style={{ width: '45%' }}
            title="0 to 28.55 RPS: Deflect to Serverless ($0 Idle Savings)"
          >
            Serverless Deflection is Cheaper (&lt; 28.55 RPS)
          </div>
          <div
            className="bg-azure-500 flex items-center justify-center transition-all"
            style={{ width: '55%' }}
            title="> 28.55 RPS: Provision AKS Node via HPA"
          >
            HPA Provisions Permanent Node (&gt; 28.55 RPS)
          </div>
        </div>

        <div className="flex items-center justify-between text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
          <span>0 RPS (Idle baseline absorbed by existing pods)</span>
          <span>Breakeven Threshold: 28.55 RPS</span>
          <span>Sustained Surge (HPA scales Kubernetes nodes)</span>
        </div>
      </div>
    </div>
  );
};
