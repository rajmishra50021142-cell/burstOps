import React from 'react';
import { BookOpen, CheckCircle, Flame, RotateCcw, TrendingUp } from 'lucide-react';

export const RunbookGuide: React.FC = () => {
  return (
    <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-6 shadow-xl space-y-5">
      <div className="pb-4 border-b border-slate-800">
        <h2 className="text-base font-semibold text-white flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-sky-400" />
          University Project Demonstration Runbook
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Step-by-step evaluator walk-through — zero terminal commands required during presentation.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        {/* Step 1 */}
        <div className="bg-slate-850 p-4 rounded-lg border border-slate-750 space-y-2">
          <div className="flex items-center gap-2 text-sky-400 font-semibold font-mono text-[11px]">
            <span className="w-5 h-5 rounded-full bg-sky-500/20 flex items-center justify-center text-xs">1</span>
            BASELINE INSPECTION
          </div>
          <p className="text-slate-300 leading-relaxed">
            Open the <strong>Grafana Dashboard</strong> link. Show the baseline state: Routing Mode is 0 (Baseline), Deflection Ratio is 0.0, and 100% of requests are handled by Kubernetes pods in the <code>burstops</code> namespace.
          </p>
        </div>

        {/* Step 2 */}
        <div className="bg-slate-850 p-4 rounded-lg border border-slate-750 space-y-2">
          <div className="flex items-center gap-2 text-amber-400 font-semibold font-mono text-[11px]">
            <span className="w-5 h-5 rounded-full bg-amber-500/20 flex items-center justify-center text-xs">2</span>
            SURGE & BURST DEFLECTION
          </div>
          <p className="text-slate-300 leading-relaxed">
            Click <strong>Generate Traffic / Simulate Burst</strong>. Watch CPU ramp past 80% in the console and Grafana. The PI controller engages, deflection ratio climbs smoothly, and requests route to Azure Functions with <code>source: serverless</code>.
          </p>
        </div>

        {/* Step 3 */}
        <div className="bg-slate-850 p-4 rounded-lg border border-slate-750 space-y-2">
          <div className="flex items-center gap-2 text-emerald-400 font-semibold font-mono text-[11px]">
            <span className="w-5 h-5 rounded-full bg-emerald-500/20 flex items-center justify-center text-xs">3</span>
            GRACEFUL RECOVERY
          </div>
          <p className="text-slate-300 leading-relaxed">
            Click <strong>Recover to Baseline</strong>. Traffic ceases. The 20% dead band (80% down to 60%) prevents flapping. As CPU decays below 60%, the gateway safely self-heals back to Kubernetes without dropped packets.
          </p>
        </div>
      </div>

      <div className="bg-slate-850/50 rounded-lg p-3.5 border border-slate-800 text-[11px] text-slate-400 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-purple-400 shrink-0" />
          <span>
            <strong>FinOps Breakeven (28.55 RPS):</strong> Baseline Kubernetes absorbs high continuous throughput; serverless scales to zero during idle periods to eliminate cloud waste.
          </span>
        </div>
        <span className="font-mono text-slate-500 shrink-0">Hysteresis: 80% / 60%</span>
      </div>
    </div>
  );
};
