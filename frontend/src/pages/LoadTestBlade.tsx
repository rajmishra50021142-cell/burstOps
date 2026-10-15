import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Flame,
  RotateCcw,
  Play,
  Square,
  Loader2,
  Cpu,
  ShieldCheck,
  CheckCircle2,
  Zap,
  Activity,
  Gauge,
  TrendingUp,
  Layers,
  Sliders,
  Server,
  AlertTriangle,
  Radio,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import {
  ActionState,
  DemoStatusResponse,
  RunDetail,
  DigitalTwinExecutionResult,
  DigitalTwinSubsystem,
  GoldenTrioTelemetry,
  LogEntry,
} from '../types';
import { sendDigitalTwinCompute, fetchGoldenTrioTelemetry } from '../lib/gatewayApi';
import { ExecutionConsole } from '../components/ExecutionConsole';

interface LoadTestBladeProps {
  status: DemoStatusResponse | null;
  onTriggerBurst: () => Promise<void>;
  onTriggerRecover: () => Promise<void>;
  isActionLoading: boolean;
}

const DEFAULT_GOLDEN_TRIO: GoldenTrioTelemetry = {
  capacity_model: {
    aks_base_capacity_slots: 10,
    active_compute_slots: 2,
    slot_saturation_pct: 20.0,
    cpu_limit: "500m (0.5 vCPU)",
    memory_limit: "512Mi",
    composite_utilization_pct: 20.0,
    explanation:
      "100% capacity = 10 concurrent heavy Digital Twin computations (500m vCPU). 80% threshold = 8 active compute slots (400m vCPU).",
  },
  novelty_1_aimd_threshold: {
    current_threshold_theta: 0.8,
    current_threshold_pct: 80.0,
    aks_p95_latency_ms: 450.0,
    slo_target_p95_ms: 650.0,
    bounds: [0.6, 0.92],
    mode: "baseline",
  },
  novelty_2_predictive_prewarm: {
    load_velocity_pct_per_s: 0.2,
    prewarm_state: "IDLE",
    prewarm_saves_count: 0,
    velocity_trigger_pct_per_s: 5.0,
    time_to_breach_trigger_s: 4.0,
  },
  novelty_3_semantic_gamma: {
    gamma_threshold: 1.5,
    subsystems: {
      MONTE_CARLO_RUL: { gamma: 9.17, policy: "Deflect to Azure Serverless" },
      ROTOR_FFT_HARMONICS: { gamma: 6.33, policy: "Deflect to Azure Serverless" },
      THERMAL_STATE_CHECK: { gamma: 0.42, policy: "Pinned to AKS Base Server" },
    },
  },
};

export const LoadTestBlade: React.FC<LoadTestBladeProps> = ({
  status,
  onTriggerBurst,
  onTriggerRecover,
  isActionLoading,
}) => {
  // Legacy status
  const currentState: ActionState = status?.state || 'Ready';
  const canBurst = Boolean(status?.can_burst && !isActionLoading);
  const canRecover = Boolean(status?.can_recover && !isActionLoading);
  const currentRun: RunDetail | undefined = status?.current_run || status?.last_completed_run || undefined;

  // Digital Twin Interactive State
  const [isTwinActive, setIsTwinActive] = useState<boolean>(false);
  const [twinId] = useState<string>(() => `WT-NORDEX-${Math.floor(10 + Math.random() * 90)}`);
  const [rpm, setRpm] = useState<number>(1800);
  const [temperatureC, setTemperatureC] = useState<number>(78);
  const [monteCarloFidelity, setMonteCarloFidelity] = useState<number>(180000);
  const [streamMultiplier, setStreamMultiplier] = useState<number>(3);
  const [isSpikeActive, setIsSpikeActive] = useState<boolean>(false);

  // Telemetry & Logs
  const [goldenTrio, setGoldenTrio] = useState<GoldenTrioTelemetry>(DEFAULT_GOLDEN_TRIO);
  const [executions, setExecutions] = useState<DigitalTwinExecutionResult[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [showLegacyCanary, setShowLegacyCanary] = useState<boolean>(false);

  // Real-time aggregate counters for this user session
  const [totalClientRequests, setTotalClientRequests] = useState<number>(0);
  const [aksRoutedCount, setAksRoutedCount] = useState<number>(0);
  const [serverlessRoutedCount, setServerlessRoutedCount] = useState<number>(0);

  // References for Web Workers and fallbacks
  const workersRef = useRef<Array<{ worker: Worker; url: string }>>([]);
  const fallbackIntervalsRef = useRef<Array<ReturnType<typeof setInterval>>>([]);

  const addLog = useCallback((level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS', message: string) => {
    const entry: LogEntry = {
      timestamp: Date.now(),
      iso_time: new Date().toISOString().substring(11, 23),
      level,
      message,
    };
    setLogs((prev) => [...prev.slice(-99), entry]);
  }, []);

  const handleExecutionResult = useCallback(
    (res: DigitalTwinExecutionResult) => {
      setExecutions((prev) => [res, ...prev.slice(0, 49)]);
      setTotalClientRequests((c) => c + 1);

      const isServerless =
        res.executed_by === 'AZURE_SERVERLESS_FUNCTION' || res.source === 'serverless';
      if (isServerless) {
        setServerlessRoutedCount((c) => c + 1);
      } else {
        setAksRoutedCount((c) => c + 1);
      }

      addLog(
        isServerless ? 'WARN' : 'SUCCESS',
        `[${res.subsystem}] Target=${res.executed_by} | Host=${res.node_hostname} | Wall=${res.wall_time_ms}ms | CPU=${res.cpu_time_ms}ms | γ=${res.gamma_ratio.toFixed(2)} | Reason=${res.routing_reason}`
      );
    },
    [addLog]
  );

  // Poll Golden Trio Status every 1.5 seconds
  useEffect(() => {
    let isMounted = true;
    const poll = async () => {
      try {
        const data = await fetchGoldenTrioTelemetry();
        if (isMounted && data?.capacity_model) {
          setGoldenTrio(data);
        }
      } catch {
        // Keep previous state gracefully
      }
    };

    poll();
    const interval = setInterval(poll, 1500);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Worker Code Template for in-browser streaming
  const createWorkerScript = () => `
    let active = true;
    let cfg = {};

    self.onmessage = function(e) {
      if (e.data.type === 'START') {
        active = true;
        cfg = e.data.config;
        loop();
      } else if (e.data.type === 'UPDATE') {
        cfg = { ...cfg, ...e.data.config };
      } else if (e.data.type === 'STOP') {
        active = false;
      }
    };

    async function loop() {
      while (active) {
        try {
          const payload = {
            twin_id: cfg.twinId,
            subsystem: cfg.subsystem,
            rpm: cfg.rpm + (Math.random() * 40 - 20),
            temperature_c: cfg.temperatureC + (Math.random() * 4 - 2),
            vibration_amplitude: 0.05 + Math.random() * 0.1,
            monte_carlo_iterations: cfg.monteCarloIterations,
          };

          const t0 = performance.now();
          const resp = await fetch('/api/twin/compute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify(payload)
          });

          if (resp.ok) {
            const data = await resp.json();
            const wall = Math.round(performance.now() - t0);
            self.postMessage({ type: 'RESULT', data: { ...data, client_wall_ms: wall, subsystem: cfg.subsystem } });
          } else {
            self.postMessage({ type: 'LOG', level: 'WARN', message: 'Compute HTTP ' + resp.status });
          }
        } catch (err) {
          self.postMessage({ type: 'LOG', level: 'ERROR', message: 'Worker compute exception: ' + (err.message || String(err)) });
        }

        const delay = cfg.delayMs || 400;
        await new Promise(r => setTimeout(r, delay));
      }
    }
  `;

  // Start/Stop Digital Twin Simulation
  useEffect(() => {
    // Clean up any existing workers or intervals
    workersRef.current.forEach(({ worker, url }) => {
      worker.terminate();
      URL.revokeObjectURL(url);
    });
    workersRef.current = [];

    fallbackIntervalsRef.current.forEach((t) => clearInterval(t));
    fallbackIntervalsRef.current = [];

    if (!isTwinActive) {
      return;
    }

    addLog(
      'INFO',
      `[TWIN START] Initializing Industrial Wind Turbine ${twinId} with ${streamMultiplier} concurrent streams.`
    );

    const subsystems: DigitalTwinSubsystem[] = [
      'MONTE_CARLO_RUL',
      'ROTOR_FFT_HARMONICS',
      'THERMAL_STATE_CHECK',
    ];

    const effectiveIterations = isSpikeActive ? 350000 : monteCarloFidelity;
    const baseDelay = isSpikeActive ? 150 : 380;

    let useWorkers = true;
    try {
      const script = createWorkerScript();
      const blob = new Blob([script], { type: 'application/javascript' });

      for (let i = 0; i < streamMultiplier; i++) {
        const subsystem = subsystems[i % subsystems.length];
        const url = URL.createObjectURL(blob);
        const worker = new Worker(url);

        worker.onmessage = (e) => {
          if (e.data.type === 'RESULT') {
            const raw = e.data.data;
            const meta = raw.gateway_metadata || {};
            const result: DigitalTwinExecutionResult = {
              id: `res-${Math.random().toString(36).substring(2, 9)}`,
              timestamp: Date.now(),
              twin_id: raw.twin_id || twinId,
              subsystem: raw.subsystem || subsystem,
              executed_by:
                raw.executed_by ||
                (raw.source === 'serverless' ? 'AZURE_SERVERLESS_FUNCTION' : 'AKS_BASE_POD'),
              source: raw.source || meta.route || 'k8s',
              impl: raw.impl || 'burstops-digital-twin',
              node_hostname: raw.node_hostname || raw.hostname || raw.instance_id || 'unknown',
              instance_id: raw.instance_id,
              process_pid: raw.process_pid,
              cpu_time_ms: raw.cpu_time_ms || 45,
              wall_time_ms: raw.wall_time_ms || e.data.client_wall_ms || 80,
              physics_output: raw.physics_output || {
                verification_hash: raw.verification_hash || 'c84f6a91...',
              },
              gamma_ratio: meta.gamma_ratio ?? (subsystem === 'THERMAL_STATE_CHECK' ? 0.42 : 8.5),
              routing_reason: meta.routing_reason ?? (raw.source === 'serverless' ? 'DEFLECTED_SERVERLESS' : 'BASELINE_K8S_NORMAL'),
              dynamic_threshold_pct: meta.dynamic_threshold_pct,
              load_velocity_pct_per_s: meta.load_velocity_pct_per_s,
              composite_utilization_pct: meta.composite_utilization_pct,
              active_compute_slots: meta.active_compute_slots,
              prewarm_state: meta.prewarm_state,
              cold_start: raw.cold_start ?? false,
            };
            handleExecutionResult(result);
          } else if (e.data.type === 'LOG') {
            addLog(e.data.level, e.data.message);
          }
        };

        worker.postMessage({
          type: 'START',
          config: {
            twinId,
            subsystem,
            rpm,
            temperatureC: isSpikeActive ? 115 : temperatureC,
            monteCarloIterations: effectiveIterations,
            delayMs: baseDelay + (i * 40),
          },
        });

        workersRef.current.push({ worker, url });
      }
    } catch (workerErr) {
      useWorkers = false;
      addLog('WARN', `Web Worker sandbox disabled; falling back to asynchronous timer loop: ${String(workerErr)}`);
    }

    // Fallback if workers were blocked
    if (!useWorkers || workersRef.current.length === 0) {
      for (let i = 0; i < streamMultiplier; i++) {
        const subsystem = subsystems[i % subsystems.length];
        const timer = setInterval(async () => {
          try {
            const res = await sendDigitalTwinCompute({
              twin_id: twinId,
              subsystem,
              rpm: rpm + (Math.random() * 40 - 20),
              temperature_c: isSpikeActive ? 115 : temperatureC,
              vibration_amplitude: 0.08,
              monte_carlo_iterations: effectiveIterations,
            });
            handleExecutionResult(res);
          } catch (err: any) {
            addLog('WARN', `Direct compute error: ${err.message || String(err)}`);
          }
        }, baseDelay + i * 50);
        fallbackIntervalsRef.current.push(timer);
      }
    }

    return () => {
      workersRef.current.forEach(({ worker, url }) => {
        worker.terminate();
        URL.revokeObjectURL(url);
      });
      workersRef.current = [];

      fallbackIntervalsRef.current.forEach((t) => clearInterval(t));
      fallbackIntervalsRef.current = [];
    };
  }, [
    isTwinActive,
    twinId,
    rpm,
    temperatureC,
    monteCarloFidelity,
    streamMultiplier,
    isSpikeActive,
    handleExecutionResult,
    addLog,
  ]);

  // Handle temporary fault spike
  const triggerFaultSpike = () => {
    setIsSpikeActive(true);
    addLog(
      'WARN',
      '[FAULT SPIKE TRIGGERED] Grid load surge active (+350k MC iterations, +20°C stator temp, fast dU/dt injection).'
    );
    setTimeout(() => {
      setIsSpikeActive(false);
      addLog('INFO', '[FAULT SPIKE CLEARED] Grid parameters normalized to baseline slider setpoints.');
    }, 12000);
  };

  const activeSlots = goldenTrio.capacity_model.active_compute_slots || 0;
  const maxSlots = goldenTrio.capacity_model.aks_base_capacity_slots || 10;
  const compositeU = goldenTrio.capacity_model.composite_utilization_pct || 0;
  const thresholdPct = goldenTrio.novelty_1_aimd_threshold.current_threshold_pct || 80.0;
  const p95Latency = goldenTrio.novelty_1_aimd_threshold.aks_p95_latency_ms || 450.0;
  const sloTarget = goldenTrio.novelty_1_aimd_threshold.slo_target_p95_ms || 650.0;
  const velocity = goldenTrio.novelty_2_predictive_prewarm.load_velocity_pct_per_s || 0.0;
  const prewarmState = goldenTrio.novelty_2_predictive_prewarm.prewarm_state || 'IDLE';

  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-7xl mx-auto select-none">
      {/* 1. HERO CARD: REAL USER INDUSTRIAL WIND TURBINE DIGITAL TWIN */}
      <div className="azure-card bg-white dark:bg-[#1B1A19] border border-[#EDEBE9] dark:border-[#292827] rounded-sm p-5 shadow-xs space-y-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#EDEBE9] dark:border-[#292827]">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded bg-azure-50 dark:bg-azure-950/60 text-azure-600 dark:text-azure-400">
                <Radio className="w-5 h-5 animate-pulse text-azure-500" />
              </span>
              <h2 className="text-base sm:text-lg font-bold text-[#323130] dark:text-white flex items-center gap-2">
                Real-User Wind Turbine Digital Twin
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 dark:bg-[#252423] text-azure-600 dark:text-azure-400 border border-[#EDEBE9] dark:border-[#323130]">
                  {twinId}
                </span>
              </h2>
            </div>
            <p className="text-xs text-[#605E5C] dark:text-[#A19F9D] mt-1 max-w-3xl leading-relaxed">
              Eliminating passive synthetic Locust traffic. Your real browser runs continuous multi-threaded
              physics state simulations (Monte Carlo degradation, rotor FFT harmonics, thermal finite difference).
              When multiple users visit this site, cumulative task volume naturally saturates the 10 AKS worker
              slots, driving automatic serverless bursting.
            </p>
          </div>

          {/* Quick Metrics Badge */}
          <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
            <div className="px-3 py-2 rounded bg-[#FAF9F8] dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827] text-right">
              <div className="text-[10px] text-[#605E5C] dark:text-[#A19F9D] uppercase tracking-wider font-semibold">
                Your Completed Tasks
              </div>
              <div className="font-mono text-sm font-bold text-[#323130] dark:text-white">
                {totalClientRequests}{' '}
                <span className="text-[10px] font-normal text-[#605E5C] dark:text-[#A19F9D]">
                  ({aksRoutedCount} AKS / {serverlessRoutedCount} Serverless)
                </span>
              </div>
            </div>

            <div
              className={`px-3 py-2 rounded border text-xs font-semibold flex items-center gap-2 ${
                isTwinActive
                  ? 'bg-emerald-50 dark:bg-emerald-950/60 border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300'
                  : 'bg-slate-100 dark:bg-[#252423] border-[#EDEBE9] dark:border-[#323130] text-[#605E5C] dark:text-[#A19F9D]'
              }`}
            >
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  isTwinActive ? 'bg-emerald-500 animate-ping' : 'bg-slate-400'
                }`}
              />
              {isTwinActive ? 'Digital Twin Active' : 'Digital Twin Idle'}
            </div>
          </div>
        </div>

        {/* Action Controls & Interactive Sliders */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Left Column: Primary Buttons */}
          <div className="lg:col-span-5 space-y-3">
            <button
              onClick={() => setIsTwinActive(!isTwinActive)}
              className={`w-full p-4 rounded-sm border text-left transition-all shadow-xs cursor-pointer ${
                isTwinActive
                  ? 'bg-gradient-to-r from-rose-50 via-white to-amber-50 dark:from-rose-950/40 dark:via-[#1B1A19] dark:to-amber-950/20 border-rose-400 dark:border-rose-700 hover:shadow-azureElevated'
                  : 'bg-gradient-to-r from-azure-50 via-white to-emerald-50 dark:from-azure-950/40 dark:via-[#1B1A19] dark:to-emerald-950/20 border-azure-400 dark:border-azure-700 hover:shadow-azureElevated'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono uppercase tracking-wider font-semibold text-azure-600 dark:text-azure-400">
                  {isTwinActive ? 'Live Computation Engaged' : 'Step 1: Activate Twin'}
                </span>
                {isTwinActive ? (
                  <Square className="w-4 h-4 text-rose-500 fill-rose-500" />
                ) : (
                  <Play className="w-4 h-4 text-emerald-500 fill-emerald-500" />
                )}
              </div>
              <div className="text-sm font-bold text-[#323130] dark:text-white mt-1">
                {isTwinActive ? 'Deactivate Wind Turbine Digital Twin' : 'Activate My Wind Turbine Digital Twin'}
              </div>
              <p className="text-xs text-[#605E5C] dark:text-[#A19F9D] mt-1">
                {isTwinActive
                  ? `Streaming ${streamMultiplier} parallel computation threads from your browser directly to Azure gateway.`
                  : 'Spawns 3 parallel Web Workers in your browser running continuous physics computations against the AKS cluster.'}
              </p>
            </button>

            {/* Simulate Spike Button */}
            <button
              onClick={triggerFaultSpike}
              disabled={isSpikeActive || !isTwinActive}
              className={`w-full p-3.5 rounded-sm border text-left transition-all ${
                isTwinActive && !isSpikeActive
                  ? 'bg-amber-50/70 dark:bg-amber-950/30 border-amber-300 dark:border-amber-700 hover:border-amber-500 cursor-pointer'
                  : 'bg-slate-50 dark:bg-[#1B1A19] border-[#EDEBE9] dark:border-[#292827] opacity-60 cursor-not-allowed'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-semibold text-amber-700 dark:text-amber-300">
                <span className="flex items-center gap-1.5">
                  <Flame className="w-4 h-4 text-amber-500 animate-bounce" />
                  Simulate Grid Fault / Thermal Spike
                </span>
                {isSpikeActive && <span className="text-[10px] uppercase font-mono animate-pulse">Spike Active (12s)</span>}
              </div>
              <p className="text-xs text-[#605E5C] dark:text-[#A19F9D] mt-1">
                Temporarily boosts Monte Carlo iterations to 350,000, inducing a high load velocity (dU/dt ≥ 5%/s)
                to trigger predictive serverless pre-warming.
              </p>
            </button>
          </div>

          {/* Right Column: Dynamic Sliders */}
          <div className="lg:col-span-7 bg-[#FAF9F8] dark:bg-[#11100F] p-4 rounded-sm border border-[#EDEBE9] dark:border-[#292827] space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-[#EDEBE9] dark:border-[#292827]">
              <span className="text-xs font-semibold text-[#323130] dark:text-white flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-azure-500" />
                Live Industrial Asset Setpoints
              </span>
              <span className="text-[11px] font-mono text-[#605E5C] dark:text-[#A19F9D]">
                Multi-User Cumulative Load: ~{streamMultiplier * 10}% Base Capacity
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              {/* Slider 1: RPM */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-[#323130] dark:text-white">
                  <span>Rotor Speed:</span>
                  <span className="font-mono font-bold text-azure-600 dark:text-azure-400">{rpm} RPM</span>
                </div>
                <input
                  type="range"
                  min="800"
                  max="3200"
                  step="50"
                  value={rpm}
                  onChange={(e) => setRpm(Number(e.target.value))}
                  className="w-full accent-azure-500 cursor-pointer h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none"
                />
                <div className="flex justify-between text-[10px] text-[#605E5C] dark:text-[#A19F9D]">
                  <span>800 RPM (Idle)</span>
                  <span>3200 RPM (Max Rated)</span>
                </div>
              </div>

              {/* Slider 2: Stator Temp */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-[#323130] dark:text-white">
                  <span>Stator Core Temp:</span>
                  <span
                    className={`font-mono font-bold ${
                      temperatureC > 95 ? 'text-rose-500' : 'text-emerald-500'
                    }`}
                  >
                    {isSpikeActive ? '115°C (SPIKE)' : `${temperatureC}°C`}
                  </span>
                </div>
                <input
                  type="range"
                  min="40"
                  max="130"
                  step="1"
                  value={temperatureC}
                  disabled={isSpikeActive}
                  onChange={(e) => setTemperatureC(Number(e.target.value))}
                  className="w-full accent-azure-500 cursor-pointer h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none"
                />
                <div className="flex justify-between text-[10px] text-[#605E5C] dark:text-[#A19F9D]">
                  <span>40°C (Cold)</span>
                  <span>130°C (Thermal Limit)</span>
                </div>
              </div>

              {/* Slider 3: Monte Carlo Fidelity */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-[#323130] dark:text-white">
                  <span>Monte Carlo Fidelity:</span>
                  <span className="font-mono font-bold text-purple-600 dark:text-purple-400">
                    {isSpikeActive ? '350,000' : monteCarloFidelity.toLocaleString()} iters
                  </span>
                </div>
                <input
                  type="range"
                  min="50000"
                  max="400000"
                  step="10000"
                  value={monteCarloFidelity}
                  disabled={isSpikeActive}
                  onChange={(e) => setMonteCarloFidelity(Number(e.target.value))}
                  className="w-full accent-azure-500 cursor-pointer h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none"
                />
                <div className="flex justify-between text-[10px] text-[#605E5C] dark:text-[#A19F9D]">
                  <span>50k (Fast, ~150ms)</span>
                  <span>400k (Heavy, ~800ms)</span>
                </div>
              </div>

              {/* Slider 4: Concurrent Streams per User */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-[#323130] dark:text-white">
                  <span>Concurrent Browser Streams:</span>
                  <span className="font-mono font-bold text-amber-600 dark:text-amber-400">
                    {streamMultiplier} Streams
                  </span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="9"
                  step="1"
                  value={streamMultiplier}
                  onChange={(e) => setStreamMultiplier(Number(e.target.value))}
                  className="w-full accent-azure-500 cursor-pointer h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none"
                />
                <div className="flex justify-between text-[10px] text-[#605E5C] dark:text-[#A19F9D]">
                  <span>1 (Light)</span>
                  <span>3-4 users = 9-12 slots (Burst!)</span>
                  <span>9 (Solo Burst)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 2. "80% OF WHAT?" EXPLICIT CAPACITY MODEL CARD */}
      <div className="azure-card bg-white dark:bg-[#1B1A19] border border-[#EDEBE9] dark:border-[#292827] rounded-sm p-5 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#EDEBE9] dark:border-[#292827]">
          <div>
            <h3 className="text-sm font-semibold text-[#323130] dark:text-white flex items-center gap-2">
              <Server className="w-4 h-4 text-emerald-500" />
              Explicit Capacity Architecture: &quot;80% of What?&quot;
            </h3>
            <p className="text-xs text-[#605E5C] dark:text-[#A19F9D] mt-0.5">
              The base AKS container is bounded to <strong>500m vCPU (0.5 core)</strong> and{' '}
              <strong>MAX_BASE_COMPUTE_SLOTS = 10</strong>.
            </p>
          </div>
          <div className="font-mono text-xs font-semibold px-2.5 py-1 rounded bg-[#FAF9F8] dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827]">
            Active Capacity: <span className="text-azure-600 dark:text-azure-400">{activeSlots}</span> / {maxSlots} Slots ({compositeU.toFixed(1)}% Load)
          </div>
        </div>

        {/* 10 Visual Compute Slots Grid */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-[#605E5C] dark:text-[#A19F9D]">
            <span>AKS Base Pod Concurrency Quota (10 Slots Total)</span>
            <span className="font-mono">
              Threshold Line: <strong>Slot 8 (80%)</strong>
            </span>
          </div>

          <div className="grid grid-cols-5 sm:grid-cols-10 gap-2">
            {Array.from({ length: 10 }).map((_, idx) => {
              const slotNum = idx + 1;
              const isOccupied = slotNum <= activeSlots;
              const isOverThreshold = slotNum > 8;

              return (
                <div
                  key={slotNum}
                  className={`p-2.5 rounded-sm border text-center transition-all ${
                    isOccupied
                      ? isOverThreshold
                        ? 'bg-amber-500/20 border-amber-500 text-amber-700 dark:text-amber-300 font-bold shadow-xs'
                        : 'bg-azure-500/20 border-azure-500 text-azure-700 dark:text-azure-300 font-bold shadow-xs'
                      : 'bg-[#FAF9F8] dark:bg-[#11100F] border-[#EDEBE9] dark:border-[#292827] text-slate-400 dark:text-slate-600'
                  }`}
                >
                  <div className="text-[10px] font-mono uppercase">Slot {slotNum}</div>
                  <div className="text-xs mt-1">
                    {isOccupied ? (
                      <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    ) : (
                      <span className="text-[10px] font-mono">Idle</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="p-3 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm border border-[#EDEBE9] dark:border-[#292827] text-xs text-[#605E5C] dark:text-[#A19F9D] flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>
                <strong>Physical Capacity Definition:</strong> 100% capacity = 10 concurrent heavy Digital Twin
                computations saturating the 500m vCPU limit. 80% threshold = exactly 8 active slots (400m vCPU).
              </span>
            </div>
            <div className="font-mono text-[11px] text-azure-600 dark:text-azure-400 shrink-0">
              U_total = max(active_slots / 10, cpu_utilization)
            </div>
          </div>
        </div>
      </div>

      {/* 3. THE GOLDEN TRIO NOVEL SYSTEMS MONITOR */}
      <div className="azure-card bg-white dark:bg-[#1B1A19] border border-[#EDEBE9] dark:border-[#292827] rounded-sm p-5 shadow-xs space-y-4">
        <div className="pb-3 border-b border-[#EDEBE9] dark:border-[#292827]">
          <h3 className="text-sm font-semibold text-[#323130] dark:text-white flex items-center gap-2">
            <Gauge className="w-4 h-4 text-purple-500" />
            The Golden Trio: Novelty Systems Telemetry
          </h3>
          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D] mt-0.5">
            Real-time telemetry from the three research mechanisms active in the BurstOps layer-7 gateway.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Novelty 1: Self-Tuning AIMD Threshold */}
          <div className="p-4 rounded-sm bg-[#FAF9F8] dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#323130] dark:text-white flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-azure-500" />
                Novelty 1: AIMD Threshold θ(t)
              </span>
              <span className="font-mono text-xs font-bold text-azure-600 dark:text-azure-400">
                {thresholdPct.toFixed(1)}%
              </span>
            </div>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between text-[#605E5C] dark:text-[#A19F9D]">
                <span>Rolling p95 Latency:</span>
                <span className="font-mono font-semibold text-[#323130] dark:text-white">
                  {p95Latency.toFixed(0)} ms
                </span>
              </div>
              <div className="flex justify-between text-[#605E5C] dark:text-[#A19F9D]">
                <span>SLO Target Ceiling:</span>
                <span className="font-mono text-emerald-600 dark:text-emerald-400">
                  {sloTarget.toFixed(0)} ms
                </span>
              </div>
              <div className="flex justify-between text-[#605E5C] dark:text-[#A19F9D]">
                <span>Operating Bounds:</span>
                <span className="font-mono text-slate-500">[60.0% – 92.0%]</span>
              </div>
            </div>
            <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] leading-tight border-t border-[#EDEBE9] dark:border-[#292827] pt-2">
              Multiplicative Decrease lowers θ(t) if p95 exceeds 650ms to prevent pod thrashing; Additive Increase raises θ(t) to maximize AKS FinOps cost savings.
            </p>
          </div>

          {/* Novelty 2: Predictive Pre-Warming */}
          <div className="p-4 rounded-sm bg-[#FAF9F8] dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#323130] dark:text-white flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5 text-amber-500" />
                Novelty 2: Pre-Warming (dU/dt)
              </span>
              <span
                className={`font-mono text-[11px] px-2 py-0.5 rounded font-semibold ${
                  prewarmState === 'WARM_READY'
                    ? 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300'
                    : prewarmState === 'PREWARMING_IN_FLIGHT'
                    ? 'bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 animate-pulse'
                    : 'bg-slate-100 dark:bg-[#252423] text-slate-500'
                }`}
              >
                {prewarmState}
              </span>
            </div>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between text-[#605E5C] dark:text-[#A19F9D]">
                <span>Load Velocity (dU/dt):</span>
                <span className="font-mono font-semibold text-[#323130] dark:text-white">
                  {velocity >= 0 ? `+${velocity.toFixed(2)}` : velocity.toFixed(2)}%/s
                </span>
              </div>
              <div className="flex justify-between text-[#605E5C] dark:text-[#A19F9D]">
                <span>Trigger Threshold:</span>
                <span className="font-mono text-slate-500">≥ +5.00%/s</span>
              </div>
              <div className="flex justify-between text-[#605E5C] dark:text-[#A19F9D]">
                <span>Cold Starts Saved:</span>
                <span className="font-mono font-bold text-purple-600 dark:text-purple-400">
                  {goldenTrio.novelty_2_predictive_prewarm.prewarm_saves_count} Instances
                </span>
              </div>
            </div>
            <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] leading-tight border-t border-[#EDEBE9] dark:border-[#292827] pt-2">
              Fires speculative HMAC-signed pre-warm pings to Azure Functions 4 seconds before breach, eliminating serverless cold start penalties.
            </p>
          </div>

          {/* Novelty 3: Semantic Compute-to-Communication Ratio */}
          <div className="p-4 rounded-sm bg-[#FAF9F8] dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#323130] dark:text-white flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-purple-500" />
                Novelty 3: Semantic Ratio γ
              </span>
              <span className="font-mono text-xs font-bold text-purple-600 dark:text-purple-400">
                Threshold: 1.50
              </span>
            </div>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between text-[#605E5C] dark:text-[#A19F9D]">
                <span>MONTE_CARLO_RUL:</span>
                <span className="font-mono font-bold text-purple-600 dark:text-purple-400">
                  γ ≈ 9.17 (Burst Priority)
                </span>
              </div>
              <div className="flex justify-between text-[#605E5C] dark:text-[#A19F9D]">
                <span>ROTOR_FFT:</span>
                <span className="font-mono font-bold text-amber-600 dark:text-amber-400">
                  γ ≈ 6.33 (Burst Candidate)
                </span>
              </div>
              <div className="flex justify-between text-[#605E5C] dark:text-[#A19F9D]">
                <span>THERMAL_CHECK:</span>
                <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
                  γ ≈ 0.42 (Pinned to AKS)
                </span>
              </div>
            </div>
            <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] leading-tight border-t border-[#EDEBE9] dark:border-[#292827] pt-2">
              Pins low-γ lightweight sensor checks to AKS to avoid network serialization overhead; deflects high-γ math-intensive tasks to Azure Functions.
            </p>
          </div>
        </div>
      </div>

      {/* 4. REAL-TIME EXECUTION PROVENANCE & LOG STREAM CONSOLE */}
      <ExecutionConsole
        executions={executions}
        logs={logs}
        title="Live Wind Turbine Execution Provenance Stream"
        activeRunId={currentRun?.run_id || twinId}
      />

      {/* 5. LEGACY CANARY & SYNTHETIC SURGE CONTROLLER (COLLAPSIBLE FOR BACKWARD COMPATIBILITY) */}
      <div className="azure-card bg-white dark:bg-[#1B1A19] border border-[#EDEBE9] dark:border-[#292827] rounded-sm p-4 shadow-xs">
        <button
          onClick={() => setShowLegacyCanary(!showLegacyCanary)}
          className="w-full flex items-center justify-between text-left text-xs font-semibold text-[#323130] dark:text-white cursor-pointer"
        >
          <span className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-azure-500" />
            Legacy Synthetic Canary & Mathematical Sieve Verification Controller
          </span>
          <span className="flex items-center gap-1 text-[11px] font-mono text-[#605E5C] dark:text-[#A19F9D]">
            {showLegacyCanary ? 'Hide Legacy Controls' : 'Show Legacy Controls (Locust/Canary Mode)'}
            {showLegacyCanary ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </span>
        </button>

        {showLegacyCanary && (
          <div className="mt-4 pt-4 border-t border-[#EDEBE9] dark:border-[#292827] space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Legacy Action 1: Surge */}
              <button
                onClick={onTriggerBurst}
                disabled={!canBurst}
                className={`p-3.5 rounded-sm border text-left transition-all ${
                  canBurst
                    ? 'bg-slate-50 dark:bg-[#11100F] border-azure-400 hover:shadow-xs cursor-pointer'
                    : 'bg-slate-50 dark:bg-[#11100F] border-[#EDEBE9] dark:border-[#292827] opacity-60 cursor-not-allowed'
                }`}
              >
                <div className="text-[10px] font-mono uppercase text-azure-600 dark:text-azure-400 font-semibold mb-1">
                  Legacy Action 1: Synthetic Surge
                </div>
                <div className="font-semibold text-xs text-[#323130] dark:text-white flex items-center gap-2">
                  {isActionLoading && !canBurst ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-azure-500" />
                  ) : (
                    <Play className="w-3.5 h-3.5 text-azure-500 fill-azure-500" />
                  )}
                  Run Synthetic Load Surge
                </div>
                <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] mt-1">
                  Triggers legacy synthetic traffic generator to verify backward compatibility.
                </p>
              </button>

              {/* Legacy Action 2: Recover */}
              <button
                onClick={onTriggerRecover}
                disabled={!canRecover}
                className={`p-3.5 rounded-sm border text-left transition-all ${
                  canRecover
                    ? 'bg-slate-50 dark:bg-[#11100F] border-emerald-400 hover:shadow-xs cursor-pointer'
                    : 'bg-slate-50 dark:bg-[#11100F] border-[#EDEBE9] dark:border-[#292827] opacity-60 cursor-not-allowed'
                }`}
              >
                <div className="text-[10px] font-mono uppercase text-emerald-600 dark:text-emerald-400 font-semibold mb-1">
                  Legacy Action 2: Baseline Recovery
                </div>
                <div className="font-semibold text-xs text-[#323130] dark:text-white flex items-center gap-2">
                  {isActionLoading && canRecover ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-500" />
                  ) : (
                    <RotateCcw className="w-3.5 h-3.5 text-emerald-500" />
                  )}
                  Recover Baseline (Cool &lt; 60%)
                </div>
                <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] mt-1">
                  Halts synthetic load and verifies recovery canary.
                </p>
              </button>
            </div>

            {/* Sieve boxes */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-sm bg-[#FAF9F8] dark:bg-[#11100F] border border-purple-200 dark:border-purple-800/50 font-mono space-y-1">
                <div className="flex items-center justify-between font-sans font-semibold text-purple-700 dark:text-purple-300 text-[11px]">
                  <span>Serverless Sieve Parity</span>
                  {currentRun?.serverless_verified ? (
                    <span className="text-purple-600 dark:text-purple-400">✓ VERIFIED</span>
                  ) : (
                    <span className="text-slate-400">PENDING</span>
                  )}
                </div>
                {currentRun?.burst_canary ? (
                  <div className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
                    Primes: {currentRun.burst_canary.prime_count} • Sum: {currentRun.burst_canary.prime_sum} • Source: {currentRun.burst_canary.source}
                  </div>
                ) : (
                  <div className="text-slate-400 text-[10px] italic">Awaiting burst transition sample...</div>
                )}
              </div>

              <div className="p-3 rounded-sm bg-[#FAF9F8] dark:bg-[#11100F] border border-emerald-200 dark:border-emerald-800/50 font-mono space-y-1">
                <div className="flex items-center justify-between font-sans font-semibold text-emerald-700 dark:text-emerald-300 text-[11px]">
                  <span>Kubernetes Baseline Parity</span>
                  {currentRun?.baseline_verified ? (
                    <span className="text-emerald-600 dark:text-emerald-400">✓ RECOVERED</span>
                  ) : (
                    <span className="text-slate-400">PENDING</span>
                  )}
                </div>
                {currentRun?.recovery_canary ? (
                  <div className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
                    Primes: {currentRun.recovery_canary.prime_count} • Sum: {currentRun.recovery_canary.prime_sum} • Source: {currentRun.recovery_canary.source}
                  </div>
                ) : (
                  <div className="text-slate-400 text-[10px] italic">Awaiting recovery signal sample...</div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
