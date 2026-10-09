import React, { useState } from 'react';
import {
  Flame,
  RotateCcw,
  Play,
  Loader2,
  Cpu,
  Sliders,
  Send,
  ShieldCheck,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Zap,
  Server,
  Activity,
} from 'lucide-react';
import { ActionState, DemoStatusResponse, RunDetail, LogEntry, CalculationCanary } from '../types';
import { ExecutionConsole } from '../components/ExecutionConsole';
import { setCpuSimPct, rampUpCpuSim, rampDownCpuSim, sendTestCalculate } from '../lib/gatewayApi';

interface LoadTestBladeProps {
  status: DemoStatusResponse | null;
  onTriggerBurst: () => Promise<void>;
  onTriggerRecover: () => Promise<void>;
  isActionLoading: boolean;
  logs: LogEntry[];
  activeRunId: string | null;
}

export const LoadTestBlade: React.FC<LoadTestBladeProps> = ({
  status,
  onTriggerBurst,
  onTriggerRecover,
  isActionLoading,
  logs,
  activeRunId,
}) => {
  const currentState: ActionState = status?.state || 'Ready';
  const canBurst = Boolean(status?.can_burst && !isActionLoading);
  const canRecover = Boolean(status?.can_recover && !isActionLoading);

  const currentRun: RunDetail | undefined = status?.current_run || status?.last_completed_run || undefined;

  // CPU Simulator manual control state
  const [sliderPct, setSliderPct] = useState<number>(75);
  const [simLoading, setSimLoading] = useState<boolean>(false);
  const [simFeedback, setSimFeedback] = useState<string | null>(null);

  // Direct Calculate Canary state
  const [testCanary, setTestCanary] = useState<CalculationCanary | null>(null);
  const [testCanaryLoading, setTestCanaryLoading] = useState<boolean>(false);

  const handleApplyCpuPct = async (pct: number) => {
    setSimLoading(true);
    setSimFeedback(null);
    try {
      const res = await setCpuSimPct(pct);
      setSimFeedback(res.success ? `CPU set to ${pct}%` : `Error: ${res.message}`);
    } finally {
      setSimLoading(false);
    }
  };

  const handleRampUp = async () => {
    setSimLoading(true);
    setSimFeedback(null);
    try {
      const res = await rampUpCpuSim();
      setSimFeedback(res.success ? 'CPU Ramp Up triggered' : `Error: ${res.message}`);
    } finally {
      setSimLoading(false);
    }
  };

  const handleRampDown = async () => {
    setSimLoading(true);
    setSimFeedback(null);
    try {
      const res = await rampDownCpuSim();
      setSimFeedback(res.success ? 'CPU Ramp Down triggered' : `Error: ${res.message}`);
    } finally {
      setSimLoading(false);
    }
  };

  const handleSendTestRequest = async () => {
    setTestCanaryLoading(true);
    try {
      const res = await sendTestCalculate();
      setTestCanary(res);
    } catch (err: any) {
      setTestCanary({
        source: 'error',
        impl: 'failed',
        prime_count: 0,
        prime_sum: 0,
        duration_ms: 0,
      });
    } finally {
      setTestCanaryLoading(false);
    }
  };

  const getStateBadge = (state: ActionState) => {
    switch (state) {
      case 'Ready':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold bg-slate-100 dark:bg-[#252423] text-[#323130] dark:text-[#F3F2F1] border border-[#EDEBE9] dark:border-[#323130]">
            <span className="w-2 h-2 rounded-full bg-slate-400" />
            Ready to Simulate
          </span>
        );
      case 'Starting':
      case 'Running':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 animate-pulse">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-500" />
            {state === 'Starting' ? 'Starting Traffic Generator...' : 'Generating Traffic...'}
          </span>
        );
      case 'Burst detected':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-700">
            <Flame className="w-3.5 h-3.5 text-amber-500 animate-bounce" />
            Burst Detected (CPU ≥ 80%)
          </span>
        );
      case 'Serverless deflection verified':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 border border-purple-300 dark:border-purple-700">
            <CheckCircle2 className="w-3.5 h-3.5 text-purple-500" />
            Serverless Deflection Verified
          </span>
        );
      case 'Recovery in progress':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold bg-yellow-50 dark:bg-yellow-950/60 text-yellow-700 dark:text-yellow-300 border border-yellow-300 dark:border-yellow-700 animate-pulse">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-yellow-500" />
            Recovery in Progress (Cooling &lt; 60%)
          </span>
        );
      case 'Baseline verified':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
            Baseline Verified (Self-Healed)
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold bg-slate-100 dark:bg-[#252423] text-[#323130] dark:text-[#F3F2F1]">
            {state}
          </span>
        );
    }
  };

  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-7xl mx-auto select-none">
      {/* Demonstration Controller Header Card */}
      <div className="azure-card p-5 rounded-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#EDEBE9] dark:border-[#292827]">
          <div>
            <h2 className="text-sm sm:text-base font-semibold text-[#323130] dark:text-white flex items-center gap-2">
              <Cpu className="w-4 h-4 text-azure-500" />
              Cloud Traffic Injection & Test Controller
            </h2>
            <p className="text-xs text-[#605E5C] dark:text-[#A19F9D]">
              Drive backend CPU beyond 80% to engage PI continuous deflection or recover to baseline without terminal commands.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {getStateBadge(currentState)}
            {currentRun && (
              <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-100 dark:bg-black/40 text-azure-600 dark:text-azure-400 border border-[#EDEBE9] dark:border-[#292827]">
                RUN: {currentRun.run_id} ({currentRun.elapsed_seconds}s)
              </span>
            )}
          </div>
        </div>

        {/* Primary Action Buttons (Button 1 and Button 2 preserved) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Button 1: Generate Traffic / Simulate Burst */}
          <button
            onClick={onTriggerBurst}
            disabled={!canBurst}
            className={`p-4 rounded-sm border text-left transition-all ${
              canBurst
                ? 'bg-gradient-to-r from-azure-50/80 via-white to-amber-50/30 dark:from-azure-950/40 dark:via-[#1B1A19] dark:to-amber-950/20 border-azure-400 dark:border-azure-700 hover:shadow-azureElevated cursor-pointer group'
                : 'bg-slate-50 dark:bg-[#1B1A19] border-[#EDEBE9] dark:border-[#292827] opacity-60 cursor-not-allowed'
            }`}
          >
            <div className="text-[11px] uppercase font-mono tracking-wider text-azure-600 dark:text-azure-400 font-semibold mb-1">
              Action 1: Load Surge
            </div>
            <div className="font-semibold text-sm text-[#323130] dark:text-white flex items-center gap-2">
              {isActionLoading && !canBurst ? (
                <Loader2 className="w-4 h-4 animate-spin text-azure-500" />
              ) : (
                <Play className="w-4 h-4 text-azure-500 fill-azure-500" />
              )}
              Generate Traffic / Simulate Burst
            </div>
            <p className="text-xs text-[#605E5C] dark:text-[#A19F9D] mt-1.5 leading-relaxed">
              Launches bounded real traffic through the Azure gateway. Drives CPU past 80% to engage the PI deflection controller.
            </p>
            {canBurst && (
              <div className="mt-2 text-[11px] font-mono text-azure-600 dark:text-azure-400 flex items-center gap-1.5 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-azure-500 animate-ping" />
                Click to initiate traffic surge
              </div>
            )}
          </button>

          {/* Button 2: Recover to Baseline */}
          <button
            onClick={onTriggerRecover}
            disabled={!canRecover}
            className={`p-4 rounded-sm border text-left transition-all ${
              canRecover
                ? 'bg-gradient-to-r from-emerald-50/80 via-white to-slate-50 dark:from-emerald-950/40 dark:via-[#1B1A19] dark:to-slate-900 border-emerald-400 dark:border-emerald-700 hover:shadow-azureElevated cursor-pointer group'
                : 'bg-slate-50 dark:bg-[#1B1A19] border-[#EDEBE9] dark:border-[#292827] opacity-60 cursor-not-allowed'
            }`}
          >
            <div className="text-[11px] uppercase font-mono tracking-wider text-emerald-600 dark:text-emerald-400 font-semibold mb-1">
              Action 2: Self-Healing
            </div>
            <div className="font-semibold text-sm text-[#323130] dark:text-white flex items-center gap-2">
              {isActionLoading && canRecover ? (
                <Loader2 className="w-4 h-4 animate-spin text-emerald-500" />
              ) : (
                <RotateCcw className="w-4 h-4 text-emerald-500" />
              )}
              Recover to Baseline
            </div>
            <p className="text-xs text-[#605E5C] dark:text-[#A19F9D] mt-1.5 leading-relaxed">
              Halts active load generation. Allows backend CPU to naturally cool below 60% and returns 100% of routing to Kubernetes.
            </p>
            {canRecover && (
              <div className="mt-2 text-[11px] font-mono text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
                Click to stop load and verify baseline
              </div>
            )}
          </button>
        </div>

        {/* Sieve of Eratosthenes Verification Canaries (Preserved!) */}
        {(currentRun?.burst_canary || currentRun?.recovery_canary) && (
          <div className="p-3.5 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm border border-[#EDEBE9] dark:border-[#292827] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#323130] dark:text-white flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-azure-500" />
                Cryptographic & Mathematical Parity Canaries (Sieve 2..1000)
              </span>
              <span className="text-[11px] font-mono text-[#605E5C] dark:text-[#A19F9D]">
                Work Parity: 168 Primes / Sum: 76,127
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              {/* Burst Canary */}
              <div className="p-3 rounded-sm bg-white dark:bg-[#1B1A19] border border-purple-200 dark:border-purple-900/60 font-mono space-y-1">
                <div className="flex items-center justify-between font-sans font-semibold text-purple-700 dark:text-purple-300 text-[11px]">
                  <span>Burst Serverless Verification</span>
                  {currentRun.serverless_verified ? (
                    <span className="text-purple-600 dark:text-purple-400">✓ VERIFIED</span>
                  ) : (
                    <span className="text-slate-400">PENDING</span>
                  )}
                </div>
                {currentRun.burst_canary ? (
                  <>
                    <div className="text-[#323130] dark:text-white">
                      Source: <strong className="text-purple-600 dark:text-purple-400">{currentRun.burst_canary.source}</strong> ({currentRun.burst_canary.impl})
                    </div>
                    <div className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
                      Instance: {currentRun.burst_canary.instance_id || 'azure-function-flex'} • Cold Start: {String(currentRun.burst_canary.cold_start)}
                    </div>
                    <div className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
                      Primes: {currentRun.burst_canary.prime_count} • Sum: {currentRun.burst_canary.prime_sum}
                    </div>
                  </>
                ) : (
                  <div className="text-slate-400 text-[11px] italic">Awaiting burst transition sample...</div>
                )}
              </div>

              {/* Recovery Canary */}
              <div className="p-3 rounded-sm bg-white dark:bg-[#1B1A19] border border-emerald-200 dark:border-emerald-900/60 font-mono space-y-1">
                <div className="flex items-center justify-between font-sans font-semibold text-emerald-700 dark:text-emerald-300 text-[11px]">
                  <span>Baseline Kubernetes Verification</span>
                  {currentRun.baseline_verified ? (
                    <span className="text-emerald-600 dark:text-emerald-400">✓ RECOVERED</span>
                  ) : (
                    <span className="text-slate-400">PENDING</span>
                  )}
                </div>
                {currentRun.recovery_canary ? (
                  <>
                    <div className="text-[#323130] dark:text-white">
                      Source: <strong className="text-emerald-600 dark:text-emerald-400">{currentRun.recovery_canary.source}</strong> ({currentRun.recovery_canary.impl})
                    </div>
                    <div className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
                      Pod Host: {currentRun.recovery_canary.hostname || 'aks-pod-dummy-backend'}
                    </div>
                    <div className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
                      Primes: {currentRun.recovery_canary.prime_count} • Sum: {currentRun.recovery_canary.prime_sum}
                    </div>
                  </>
                ) : (
                  <div className="text-slate-400 text-[11px] italic">Awaiting recovery baseline sample...</div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Direct CPU Simulation Knobs (port 8002) & Single Calculate Canary */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* CPU Simulator Knobs */}
        <div className="azure-card p-4 rounded-sm space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-xs text-[#323130] dark:text-white flex items-center gap-1.5">
              <Sliders className="w-4 h-4 text-azure-500" />
              Deterministic CPU-Sim Knobs (Port 8002)
            </h3>
            {simFeedback && (
              <span className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400 font-semibold">
                {simFeedback}
              </span>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#605E5C] dark:text-[#A19F9D]">Target Simulated CPU:</span>
              <span className="font-mono font-bold text-azure-600 dark:text-azure-400">{sliderPct}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={sliderPct}
              onChange={(e) => setSliderPct(Number(e.target.value))}
              className="w-full accent-azure-500 cursor-pointer"
            />
          </div>

          {/* Preset Buttons */}
          <div className="grid grid-cols-4 gap-2 text-xs">
            <button
              onClick={() => { setSliderPct(25); handleApplyCpuPct(25); }}
              disabled={simLoading}
              className="p-1.5 bg-[#FAF9F8] dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827] rounded hover:border-azure-500 text-center transition-colors"
            >
              25% Idle
            </button>
            <button
              onClick={() => { setSliderPct(50); handleApplyCpuPct(50); }}
              disabled={simLoading}
              className="p-1.5 bg-[#FAF9F8] dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827] rounded hover:border-azure-500 text-center transition-colors"
            >
              50% Normal
            </button>
            <button
              onClick={() => { setSliderPct(75); handleApplyCpuPct(75); }}
              disabled={simLoading}
              className="p-1.5 bg-[#FAF9F8] dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827] rounded hover:border-azure-500 text-center transition-colors"
            >
              75% Warm
            </button>
            <button
              onClick={() => { setSliderPct(90); handleApplyCpuPct(90); }}
              disabled={simLoading}
              className="p-1.5 bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-700 text-amber-700 dark:text-amber-300 font-semibold rounded text-center transition-colors"
            >
              90% Surge
            </button>
          </div>

          <div className="flex gap-2 pt-1">
            <button
              onClick={() => handleApplyCpuPct(sliderPct)}
              disabled={simLoading}
              className="azure-btn-primary flex-1"
            >
              {simLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Apply CPU Setpoint'}
            </button>
            <button
              onClick={handleRampUp}
              disabled={simLoading}
              className="azure-btn-secondary"
              title="Ramp Up CPU"
            >
              Ramp Up ↑
            </button>
            <button
              onClick={handleRampDown}
              disabled={simLoading}
              className="azure-btn-secondary"
              title="Ramp Down CPU"
            >
              Ramp Down ↓
            </button>
          </div>
        </div>

        {/* Single Test Request Canary Tester */}
        <div className="azure-card p-4 rounded-sm space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-xs text-[#323130] dark:text-white flex items-center gap-1.5">
              <Send className="w-4 h-4 text-azure-500" />
              Live Upstream Canary Probe (GET /calculate)
            </h3>
            <button
              onClick={handleSendTestRequest}
              disabled={testCanaryLoading}
              className="azure-btn-primary text-xs"
            >
              {testCanaryLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Send Probe'}
            </button>
          </div>

          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D]">
            Sends a single live HTTP request through the gateway to inspect which upstream target responds in real time.
          </p>

          {testCanary ? (
            <div className="p-3 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm border border-[#EDEBE9] dark:border-[#292827] font-mono text-xs space-y-1.5">
              <div className="flex justify-between items-center">
                <span className="text-[#605E5C] dark:text-[#A19F9D]">Upstream Responder:</span>
                <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                  testCanary.source === 'serverless' || testCanary.source === 'azure_function'
                    ? 'bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300'
                    : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                }`}>
                  {testCanary.source.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#605E5C] dark:text-[#A19F9D]">Implementation:</span>
                <span>{testCanary.impl}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#605E5C] dark:text-[#A19F9D]">Canary Work Verification:</span>
                <span className="text-azure-600 dark:text-azure-400">
                  {testCanary.prime_count} primes (Sum: {testCanary.prime_sum})
                </span>
              </div>
              {testCanary.duration_ms !== undefined && (
                <div className="flex justify-between">
                  <span className="text-[#605E5C] dark:text-[#A19F9D]">Roundtrip Latency:</span>
                  <span>{testCanary.duration_ms} ms</span>
                </div>
              )}
            </div>
          ) : (
            <div className="p-6 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm border border-dashed border-[#EDEBE9] dark:border-[#292827] text-center text-slate-400 text-xs">
              Click "Send Probe" to sample the live upstream target.
            </div>
          )}
        </div>
      </div>

      {/* Cloud Shell / Execution Stream Console */}
      <ExecutionConsole logs={logs} activeRunId={activeRunId} title="Cloud Shell — Real Execution Stream" />
    </div>
  );
};
