import React, { useEffect, useRef, useState } from 'react';
import { Terminal, Copy, Check, ArrowDownCircle, Cpu, Zap, Activity } from 'lucide-react';
import { DigitalTwinExecutionResult, LogEntry } from '../types';

interface ExecutionConsoleProps {
  logs: LogEntry[];
  executions?: DigitalTwinExecutionResult[];
  title?: string;
  activeRunId?: string | null;
}

export const ExecutionConsole: React.FC<ExecutionConsoleProps> = ({
  logs,
  executions = [],
  title = "Real Execution Output & Provenance Stream",
  activeRunId,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<'provenance' | 'logs'>('provenance');

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, executions, autoScroll]);

  const handleCopyLogs = () => {
    let text = "";
    if (activeTab === 'logs') {
      text = logs.map((l) => `[${l.iso_time}] [${l.level}] ${l.message}`).join('\n');
    } else {
      text = executions.map((e) => 
        `[${new Date(e.timestamp).toLocaleTimeString()}] Subsystem=${e.subsystem} ExecutedBy=${e.executed_by} Host=${e.node_hostname} WallMs=${e.wall_time_ms} CPUMs=${e.cpu_time_ms} Gamma=${e.gamma_ratio} Reason=${e.routing_reason} Hash=${e.physics_output.verification_hash}`
      ).join('\n');
    }
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'SUCCESS':
        return 'text-emerald-400 font-semibold';
      case 'WARN':
        return 'text-amber-400 font-semibold';
      case 'ERROR':
        return 'text-rose-400 font-semibold';
      case 'INFO':
      default:
        return 'text-cyan-400';
    }
  };

  return (
    <div className="bg-slate-950 rounded-xl border border-slate-800 shadow-2xl overflow-hidden font-mono text-xs">
      {/* Terminal Title Bar */}
      <div className="bg-slate-900 px-4 py-2.5 border-b border-slate-800 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          {/* Mac-style window controls */}
          <div className="flex items-center gap-1.5 mr-2">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80 inline-block"></span>
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80 inline-block"></span>
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80 inline-block"></span>
          </div>
          <Terminal className="w-4 h-4 text-slate-400" />
          <span className="text-slate-300 font-sans font-medium text-xs">
            {title}
          </span>
          {activeRunId && (
            <span className="text-[11px] text-cyan-400 font-mono px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700">
              {activeRunId}
            </span>
          )}
        </div>

        {/* Tab switchers */}
        <div className="flex items-center gap-2 font-sans">
          <div className="flex bg-slate-800/80 p-0.5 rounded border border-slate-700 text-[11px]">
            <button
              onClick={() => setActiveTab('provenance')}
              className={`px-2.5 py-1 rounded transition-colors flex items-center gap-1.5 ${
                activeTab === 'provenance'
                  ? 'bg-azure-600 text-white font-medium shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="w-3 h-3" />
              <span>Digital Twin Provenance ({executions.length})</span>
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`px-2.5 py-1 rounded transition-colors flex items-center gap-1.5 ${
                activeTab === 'logs'
                  ? 'bg-azure-600 text-white font-medium shadow-xs'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Terminal className="w-3 h-3" />
              <span>System Logs ({logs.length})</span>
            </button>
          </div>

          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`px-2 py-1 rounded text-[11px] flex items-center gap-1 transition-colors ${
              autoScroll
                ? 'bg-blue-900/50 text-blue-300 border border-blue-700/50'
                : 'bg-slate-800 text-slate-400 border border-slate-700'
            }`}
            title={autoScroll ? 'Auto-scroll enabled' : 'Auto-scroll paused'}
          >
            <ArrowDownCircle className="w-3 h-3" />
            <span>{autoScroll ? 'Scroll: ON' : 'Scroll: OFF'}</span>
          </button>

          <button
            onClick={handleCopyLogs}
            className="px-2 py-1 rounded text-[11px] bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700 flex items-center gap-1 transition-colors"
            title="Copy content to clipboard"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 text-emerald-400" />
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-3 text-slate-400" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Terminal Content Stream */}
      <div
        ref={containerRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          const isAtBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 40;
          if (!isAtBottom && autoScroll) {
            setAutoScroll(false);
          }
        }}
        className="p-4 h-80 overflow-y-auto terminal-scroll bg-slate-950 space-y-1.5 leading-relaxed"
      >
        {activeTab === 'provenance' ? (
          executions.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 font-sans space-y-1 text-center">
              <Activity className="w-8 h-8 text-slate-700 mb-1 animate-pulse" />
              <p className="text-xs font-semibold text-slate-400">Digital Twin Telemetry Stream Idle</p>
              <p className="text-[11px] text-slate-500 max-w-md">
                Click "Activate My Wind Turbine Digital Twin" above. Real browser Web Workers will stream calculations through the gateway, showing live AKS vs Serverless execution provenance proofs here.
              </p>
            </div>
          ) : (
            executions.map((item) => {
              const isServerless = item.executed_by.includes("SERVERLESS") || item.source === "serverless";
              return (
                <div
                  key={item.id}
                  className={`p-2 rounded border transition-all text-[11px] space-y-1 ${
                    isServerless
                      ? 'bg-purple-950/25 border-purple-800/60 hover:bg-purple-950/40 text-purple-200'
                      : 'bg-blue-950/25 border-blue-800/60 hover:bg-blue-950/40 text-blue-200'
                  }`}
                >
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400 font-mono text-[10px]">
                        {new Date(item.timestamp).toLocaleTimeString()}
                      </span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase flex items-center gap-1 ${
                          isServerless
                            ? 'bg-purple-600 text-white'
                            : 'bg-azure-600 text-white'
                        }`}
                      >
                        {isServerless ? <Zap className="w-2.5 h-2.5" /> : <Cpu className="w-2.5 h-2.5" />}
                        {item.executed_by}
                      </span>
                      <span className="font-semibold text-white tracking-wide">
                        {item.subsystem}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 font-mono text-[10px]">
                      <span className="text-amber-400 bg-amber-950/50 px-1 py-0.5 rounded border border-amber-800/40">
                        γ = {item.gamma_ratio}
                      </span>
                      <span className="text-slate-300">
                        {item.routing_reason}
                      </span>
                      <span className="text-emerald-400 font-semibold">
                        Wall: {item.wall_time_ms}ms (CPU: {item.cpu_time_ms}ms)
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono pt-0.5 border-t border-slate-800/50">
                    <span className="truncate max-w-sm">
                      Host: <strong className="text-slate-300">{item.node_hostname}</strong> (PID: {item.process_pid ?? 'N/A'})
                    </span>
                    <span className="truncate max-w-xs text-slate-500">
                      SHA256: {item.physics_output.verification_hash?.substring(0, 16)}...
                    </span>
                    {item.cold_start && (
                      <span className="text-amber-300 bg-amber-900/50 px-1 rounded text-[9px]">
                        COLD START
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )
        ) : logs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 font-sans space-y-1">
            <Terminal className="w-8 h-8 text-slate-700 mb-1" />
            <p className="text-xs">Console is idle. Click "Generate Traffic / Simulate Burst" to start.</p>
          </div>
        ) : (
          logs.map((log, idx) => (
            <div key={`${log.timestamp}-${idx}`} className="flex items-start gap-2 hover:bg-slate-900/40 py-0.5 px-1 rounded transition-colors">
              <span className="text-slate-500 text-[11px] select-none shrink-0 font-mono">
                {log.iso_time}
              </span>
              <span className={`text-[11px] shrink-0 font-mono w-16 ${getLevelColor(log.level)}`}>
                [{log.level}]
              </span>
              <span className={`text-slate-200 break-words ${log.level === 'SUCCESS' ? 'text-emerald-200' : ''}`}>
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>

      {/* Terminal Footer */}
      <div className="bg-slate-900/70 px-4 py-1.5 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400 font-sans">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
          <span>Proof of Execution: Genuine CPU computation verified by cryptographic hash</span>
        </div>
        <span>
          {activeTab === 'provenance' ? `${executions.length} calculations completed` : `${logs.length} system lines`}
        </span>
      </div>
    </div>
  );
};
