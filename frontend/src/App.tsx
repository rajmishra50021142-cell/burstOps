import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Header } from './components/Header';
import { ArchitectureDiagram } from './components/ArchitectureDiagram';
import { DemoControl } from './components/DemoControl';
import { ExecutionConsole } from './components/ExecutionConsole';
import { ResourceLinks } from './components/ResourceLinks';
import { RunbookGuide } from './components/RunbookGuide';
import { fetchDemoStatus, triggerBurst, triggerRecovery } from './api';
import { DemoStatusResponse, LogEntry } from './types';
import { AlertCircle, RefreshCw } from 'lucide-react';

export const App: React.FC = () => {
  const [status, setStatus] = useState<DemoStatusResponse | null>(null);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const isPollingRef = useRef(false);

  const pollStatus = useCallback(async () => {
    if (isPollingRef.current) return;
    isPollingRef.current = true;
    try {
      const data = await fetchDemoStatus();
      setStatus(data);
      setErrorMessage(null);
    } catch (err: any) {
      // Don't spam error message on transient poll failures
      if (!status) {
        setErrorMessage(err.message || 'Connecting to BurstOps control service...');
      }
    } finally {
      isPollingRef.current = false;
    }
  }, [status]);

  useEffect(() => {
    // Initial fetch
    pollStatus();

    // Regular polling every 2s
    const timer = setInterval(() => {
      pollStatus();
    }, 2000);

    return () => clearInterval(timer);
  }, [pollStatus]);

  const handleTriggerBurst = async () => {
    setIsActionLoading(true);
    setErrorMessage(null);
    try {
      await triggerBurst();
      await pollStatus();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to start burst experiment.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleTriggerRecover = async () => {
    setIsActionLoading(true);
    setErrorMessage(null);
    try {
      await triggerRecovery();
      await pollStatus();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to trigger recovery.');
    } finally {
      setIsActionLoading(false);
    }
  };

  // Determine active logs to display (active run or previous completed run)
  const activeRun = status?.current_run || status?.last_completed_run;
  const logs: LogEntry[] = activeRun?.logs || [];
  const activeRunId = activeRun?.run_id || null;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col selection:bg-blue-600 selection:text-white">
      <Header />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Error notification banner if any */}
        {errorMessage && (
          <div className="rounded-lg bg-rose-950/60 border border-rose-500/50 p-4 flex items-center justify-between text-rose-200 text-xs shadow-lg">
            <div className="flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{errorMessage}</span>
            </div>
            <button
              onClick={() => pollStatus()}
              className="px-2.5 py-1 rounded bg-rose-900/60 hover:bg-rose-900 text-rose-200 border border-rose-700/50 text-[11px] flex items-center gap-1 transition-colors"
            >
              <RefreshCw className="w-3 h-3" />
              Retry
            </button>
          </div>
        )}

        {/* Section A: Architecture Overview */}
        <ArchitectureDiagram />

        {/* Section B: Live Demonstration Controller */}
        <DemoControl
          status={status}
          onTriggerBurst={handleTriggerBurst}
          onTriggerRecover={handleTriggerRecover}
          isActionLoading={isActionLoading}
        />

        {/* Section B / Console: Real Execution Stream */}
        <ExecutionConsole logs={logs} activeRunId={activeRunId} />

        {/* Section B & C: Ordered Resource Deep-Links */}
        {status?.ordered_links && status.ordered_links.length > 0 && (
          <ResourceLinks
            heading={status.links_heading}
            links={status.ordered_links}
          />
        )}

        {/* Section D: Runbook Guide */}
        <RunbookGuide />
      </main>

      <footer className="border-t border-slate-900 py-6 mt-8 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span>BurstOps — Elastic Serverless Burst Gateway &copy; 2026</span>
          <div className="flex items-center gap-4">
            <span className="font-mono text-slate-600">Option A: 100% Cloud Architecture</span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            <span className="text-slate-400">Azure centralindia</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
