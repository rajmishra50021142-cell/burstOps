import React, { useEffect, useRef, useState } from 'react';
import { Terminal, Copy, Check, ArrowDownCircle, ShieldAlert } from 'lucide-react';
import { LogEntry } from '../types';

interface ExecutionConsoleProps {
  logs: LogEntry[];
  title?: string;
  activeRunId?: string | null;
}

export const ExecutionConsole: React.FC<ExecutionConsoleProps> = ({
  logs,
  title = "Real Execution Output & State Machine Stream",
  activeRunId,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleCopyLogs = () => {
    const text = logs
      .map((l) => `[${l.iso_time}] [${l.level}] ${l.message}`)
      .join('\n');
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
      <div className="bg-slate-900 px-4 py-2.5 border-b border-slate-800 flex items-center justify-between">
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

        <div className="flex items-center gap-2 font-sans">
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
            <span>{autoScroll ? 'Auto-scroll: ON' : 'Auto-scroll: OFF'}</span>
          </button>

          <button
            onClick={handleCopyLogs}
            disabled={logs.length === 0}
            className="px-2 py-1 rounded text-[11px] bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700 flex items-center gap-1 transition-colors disabled:opacity-50"
            title="Copy all logs to clipboard"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 text-emerald-400" />
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-3 text-slate-400" />
                <span>Copy Logs</span>
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
        {logs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 font-sans space-y-1">
            <Terminal className="w-8 h-8 text-slate-700 mb-1" />
            <p className="text-xs">Console is idle. Click "Generate Traffic / Simulate Burst" to start.</p>
            <p className="text-[11px] text-slate-600">
              Real telemetry, CPU ramp notifications, and serverless deflection verification will stream here.
            </p>
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
          <span>Redaction: Tokens & Secrets Automatically Masked</span>
        </div>
        <span>{logs.length} lines logged</span>
      </div>
    </div>
  );
};
