import React from 'react';
import { Play, RotateCcw, Loader2, CheckCircle2, AlertTriangle, Clock, ShieldCheck, Flame, Cpu } from 'lucide-react';
import { ActionState, DemoStatusResponse, RunDetail } from '../types';

interface DemoControlProps {
  status: DemoStatusResponse | null;
  onTriggerBurst: () => Promise<void>;
  onTriggerRecover: () => Promise<void>;
  isActionLoading: boolean;
}

export const DemoControl: React.FC<DemoControlProps> = ({
  status,
  onTriggerBurst,
  onTriggerRecover,
  isActionLoading,
}) => {
  const currentState: ActionState = status?.state || 'Ready';
  const canBurst = Boolean(status?.can_burst && !isActionLoading);
  const canRecover = Boolean(status?.can_recover && !isActionLoading);

  // Active run or most recently completed run for reference
  const currentRun: RunDetail | undefined = status?.current_run || status?.last_completed_run || undefined;

  const getStateBadge = (state: ActionState) => {
    switch (state) {
      case 'Ready':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
            <span className="w-2 h-2 rounded-full bg-slate-400"></span>
            Ready to Run
          </span>
        );
      case 'Starting':
      case 'Running':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-900/60 text-blue-300 border border-blue-600/50 animate-pulse">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" />
            {state === 'Starting' ? 'Starting Load Generator...' : 'Generating Cloud Traffic...'}
          </span>
        );
      case 'Burst detected':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-900/60 text-amber-300 border border-amber-600/50">
            <Flame className="w-3.5 h-3.5 text-amber-400 animate-bounce" />
            Burst Detected (CPU &ge; 80%)
          </span>
        );
      case 'Serverless deflection verified':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-purple-900/60 text-purple-200 border border-purple-500/60">
            <CheckCircle2 className="w-3.5 h-3.5 text-purple-400" />
            Serverless Deflection Verified
          </span>
        );
      case 'Recovery in progress':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-yellow-900/60 text-yellow-300 border border-yellow-600/50 animate-pulse">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-yellow-400" />
            Recovery in Progress (Cooling down &lt; 60%)
          </span>
        );
      case 'Baseline verified':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-900/60 text-emerald-200 border border-emerald-600/50">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            Baseline Verified (Self-Healed)
          </span>
        );
      case 'Timed out':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-orange-900/60 text-orange-200 border border-orange-600/50">
            <Clock className="w-3.5 h-3.5 text-orange-400" />
            Timed Out
          </span>
        );
      case 'Failed':
      case 'Cancelled':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-900/60 text-rose-200 border border-rose-600/50">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
            {state}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300">
            {state}
          </span>
        );
    }
  };

  return (
    <div className="bg-slate-900/80 rounded-xl border border-slate-800 p-6 shadow-xl space-y-6">
      {/* Header and Status Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-800">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Cpu className="w-5 h-5 text-blue-400" />
            Live Cloud Demonstration Controller
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Trigger real traffic generation against the live Azure deployment without touching the terminal.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {getStateBadge(currentState)}

          {currentRun && (
            <div className="flex items-center gap-2 text-xs font-mono bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700 text-slate-300">
              <span className="text-slate-500">RUN:</span>
              <span className="text-cyan-300 font-semibold">{currentRun.run_id}</span>
              {currentRun.elapsed_seconds > 0 && (
                <>
                  <span className="text-slate-600">•</span>
                  <span className="text-slate-400">{currentRun.elapsed_seconds}s</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Primary Action Buttons */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Button 1: Generate Traffic / Simulate Burst */}
        <button
          onClick={onTriggerBurst}
          disabled={!canBurst}
          className={`relative group overflow-hidden rounded-xl p-5 text-left transition-all duration-200 border ${
            canBurst
              ? 'bg-gradient-to-br from-blue-900/50 via-slate-850 to-blue-950/40 border-blue-500/40 hover:border-blue-400 hover:shadow-lg hover:shadow-blue-500/10 cursor-pointer active:scale-[0.99]'
              : 'bg-slate-850/50 border-slate-800 opacity-60 cursor-not-allowed'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <div className="text-xs uppercase font-mono tracking-wider text-blue-400 font-semibold">
                Action 1
              </div>
              <div className="text-base font-bold text-white flex items-center gap-2">
                {isActionLoading && !canBurst ? (
                  <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
                ) : (
                  <Play className="w-5 h-5 text-blue-400 fill-blue-400" />
                )}
                Generate Traffic / Simulate Burst
              </div>
              <p className="text-xs text-slate-400 max-w-sm mt-1">
                Launches bounded real traffic through the existing Azure gateway. Drives backend CPU past 80% to engage the PI deflection controller.
              </p>
            </div>
          </div>
          {canBurst && (
            <div className="mt-3 text-[11px] font-mono text-blue-300/80 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping"></span>
              Click to initiate traffic surge
            </div>
          )}
        </button>

        {/* Button 2: Recover to Baseline */}
        <button
          onClick={onTriggerRecover}
          disabled={!canRecover}
          className={`relative group overflow-hidden rounded-xl p-5 text-left transition-all duration-200 border ${
            canRecover
              ? 'bg-gradient-to-br from-emerald-950/40 via-slate-850 to-slate-850 border-emerald-500/40 hover:border-emerald-400 hover:shadow-lg hover:shadow-emerald-500/10 cursor-pointer active:scale-[0.99]'
              : 'bg-slate-850/50 border-slate-800 opacity-60 cursor-not-allowed'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <div className="text-xs uppercase font-mono tracking-wider text-emerald-400 font-semibold">
                Action 2
              </div>
              <div className="text-base font-bold text-white flex items-center gap-2">
                {isActionLoading && canRecover ? (
                  <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
                ) : (
                  <RotateCcw className="w-5 h-5 text-emerald-400" />
                )}
                Recover to Baseline
              </div>
              <p className="text-xs text-slate-400 max-w-sm mt-1">
                Halts active traffic generation. Allows the controller to cool below the 60% recovery threshold naturally and return routing to Kubernetes.
              </p>
            </div>
          </div>
          {canRecover && (
            <div className="mt-3 text-[11px] font-mono text-emerald-300/80 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
              Click to stop load and verify baseline
            </div>
          )}
        </button>
      </div>

      {/* Sieve of Eratosthenes Verification Canaries (Preserved across both stages) */}
      {(currentRun?.burst_canary || currentRun?.recovery_canary) && (
        <div className="bg-slate-850/80 rounded-lg border border-slate-750 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
              Cryptographic & Mathematical Parity Canaries (Sieve 2..1000)
            </span>
            <span className="text-[11px] font-mono text-slate-400">
              Work Canary: 168 Primes / Sum: 76,127
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            {/* Burst Canary */}
            <div className="bg-slate-900 p-3 rounded border border-purple-500/30 space-y-1 font-mono">
              <div className="flex items-center justify-between text-[11px] font-sans font-semibold text-purple-300">
                <span>Burst Serverless Verification</span>
                {currentRun.serverless_verified ? (
                  <span className="text-purple-400 flex items-center gap-1">✓ VERIFIED</span>
                ) : (
                  <span className="text-slate-400">PENDING</span>
                )}
              </div>
              {currentRun.burst_canary ? (
                <>
                  <div className="text-slate-300">
                    Source: <strong className="text-purple-400">{currentRun.burst_canary.source}</strong> (impl: {currentRun.burst_canary.impl})
                  </div>
                  <div className="text-slate-400 text-[11px]">
                    Instance: {currentRun.burst_canary.instance_id || 'remote'} • Cold Start: {String(currentRun.burst_canary.cold_start)}
                  </div>
                  <div className="text-slate-400 text-[11px]">
                    Primes: {currentRun.burst_canary.prime_count} • Sum: {currentRun.burst_canary.prime_sum}
                  </div>
                </>
              ) : (
                <div className="text-slate-500 text-[11px] italic">Awaiting burst transition and deflection sample...</div>
              )}
            </div>

            {/* Recovery Canary */}
            <div className="bg-slate-900 p-3 rounded border border-emerald-500/30 space-y-1 font-mono">
              <div className="flex items-center justify-between text-[11px] font-sans font-semibold text-emerald-300">
                <span>Baseline Kubernetes Verification</span>
                {currentRun.baseline_verified ? (
                  <span className="text-emerald-400 flex items-center gap-1">✓ RECOVERED</span>
                ) : (
                  <span className="text-slate-400">PENDING</span>
                )}
              </div>
              {currentRun.recovery_canary ? (
                <>
                  <div className="text-slate-300">
                    Source: <strong className="text-emerald-400">{currentRun.recovery_canary.source}</strong> (impl: {currentRun.recovery_canary.impl})
                  </div>
                  <div className="text-slate-400 text-[11px]">
                    Host: {currentRun.recovery_canary.hostname || 'k8s-pod'}
                  </div>
                  <div className="text-slate-400 text-[11px]">
                    Primes: {currentRun.recovery_canary.prime_count} • Sum: {currentRun.recovery_canary.prime_sum}
                  </div>
                </>
              ) : (
                <div className="text-slate-500 text-[11px] italic">Awaiting recovery signal and baseline sample...</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
