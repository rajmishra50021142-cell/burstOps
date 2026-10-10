import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AzureTopBar } from './components/AzureTopBar';
import { AzureSidebar } from './components/AzureSidebar';
import { AzureBreadcrumb } from './components/AzureBreadcrumb';
import { AzureCommandBar } from './components/AzureCommandBar';

import { HomeBlade } from './pages/HomeBlade';
import { GatewayBlade } from './pages/GatewayBlade';
import { LoadTestBlade } from './pages/LoadTestBlade';

import { fetchDemoStatus, triggerBurst, triggerRecovery } from './api';
import { useMetricsHistory } from './hooks/useMetricsHistory';
import { PortalBlade, DemoStatusResponse } from './types';
import { AlertCircle, CheckCircle2, X } from 'lucide-react';

export const App: React.FC = () => {
  // Navigation & UI State (strictly Home, Gateway, Load Test)
  const [activeBlade, setActiveBlade] = useState<PortalBlade>('home');
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [theme, setTheme] = useState<'dark' | 'light'>('light'); // default light so white aesthetic is immediate
  const [feedbackToast, setFeedbackToast] = useState<string | null>(null);

  // Demo State & Polling
  const [demoStatus, setDemoStatus] = useState<DemoStatusResponse | null>(null);
  const [isActionLoading, setIsActionLoading] = useState<boolean>(false);
  const [demoErrorMessage, setDemoErrorMessage] = useState<string | null>(null);
  const isDemoPollingRef = useRef<boolean>(false);

  // Gateway Telemetry Hook
  const { metrics, isOnline, poll: pollMetrics } = useMetricsHistory();

  // Initialize theme
  useEffect(() => {
    const savedTheme = (localStorage.getItem('burstops_portal_theme') as 'dark' | 'light') || 'light';
    setTheme(savedTheme);
    if (savedTheme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, []);

  const handleToggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('burstops_portal_theme', next);
    if (next === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  };

  // Poll Demo Status (/api/demo/status)
  const pollDemoStatus = useCallback(async () => {
    if (isDemoPollingRef.current) return;
    isDemoPollingRef.current = true;
    try {
      const data = await fetchDemoStatus();
      setDemoStatus(data);
      setDemoErrorMessage(null);
    } catch (err: any) {
      if (!demoStatus) {
        setDemoErrorMessage(err.message || 'Connecting to BurstOps control service...');
      }
    } finally {
      isDemoPollingRef.current = false;
    }
  }, [demoStatus]);

  useEffect(() => {
    pollDemoStatus();
    const timer = setInterval(pollDemoStatus, 2000);
    return () => clearInterval(timer);
  }, [pollDemoStatus]);

  // Actions
  const handleTriggerBurst = async () => {
    setIsActionLoading(true);
    setDemoErrorMessage(null);
    try {
      await triggerBurst();
      await pollDemoStatus();
      setFeedbackToast('Traffic surge triggered. Deflection controller engaging.');
    } catch (err: any) {
      setDemoErrorMessage(err.message || 'Failed to start burst experiment.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleTriggerRecover = async () => {
    setIsActionLoading(true);
    setDemoErrorMessage(null);
    try {
      await triggerRecovery();
      await pollDemoStatus();
      setFeedbackToast('Traffic stopped. Recovering baseline to Kubernetes.');
    } catch (err: any) {
      setDemoErrorMessage(err.message || 'Failed to trigger recovery.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRefreshAll = () => {
    pollDemoStatus();
    pollMetrics();
    setFeedbackToast('Data refreshed');
  };

  // Auto-dismiss toast
  useEffect(() => {
    if (feedbackToast) {
      const timer = setTimeout(() => setFeedbackToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [feedbackToast]);

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF9F8] dark:bg-[#11100F] text-[#323130] dark:text-[#F3F2F1]">
      {/* 1. Azure Portal Clean Top Bar */}
      <AzureTopBar
        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        onNavigate={(blade) => setActiveBlade(blade)}
        theme={theme}
        onToggleTheme={handleToggleTheme}
      />

      {/* Main Layout Container */}
      <div className="flex-1 flex relative">
        {/* 2. Left Sidebar (Strictly Home, Gateway, Load Test & Simulator) */}
        <AzureSidebar
          isOpen={isSidebarOpen}
          activeBlade={activeBlade}
          onNavigate={(blade) => setActiveBlade(blade)}
        />

        {/* Content Area offset by sidebar */}
        <div
          className={`flex-1 flex flex-col transition-all duration-200 min-w-0 ${
            isSidebarOpen ? 'ml-56' : 'ml-12'
          }`}
        >
          {/* 3. Breadcrumb & Title */}
          <AzureBreadcrumb
            activeBlade={activeBlade}
            onNavigate={(blade) => setActiveBlade(blade)}
            routingMode={metrics?.routingMode ?? 0}
            isOnline={isOnline}
          />

          {/* 4. Command Bar (Clean: Refresh, Simulate Burst, Recover Baseline, Grafana) */}
          <AzureCommandBar
            onRefresh={handleRefreshAll}
            onTriggerBurst={handleTriggerBurst}
            onTriggerRecover={handleTriggerRecover}
            isActionLoading={isActionLoading}
            demoStatus={demoStatus}
          />

          {/* Error Banner if service unreachable */}
          {demoErrorMessage && (
            <div className="mx-4 sm:mx-6 mt-4 p-3 bg-rose-50 dark:bg-rose-950/60 border border-rose-300 dark:border-rose-800 rounded-sm text-xs text-rose-700 dark:text-rose-300 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
                <span>{demoErrorMessage}</span>
              </div>
              <button
                onClick={() => pollDemoStatus()}
                className="azure-btn-secondary text-[11px] h-6 px-2 text-rose-700 dark:text-rose-300 border-rose-300 dark:border-rose-700"
              >
                Retry
              </button>
            </div>
          )}

          {/* 5. Main Blade Views */}
          <main className="flex-1 pb-10">
            {activeBlade === 'home' && (
              <HomeBlade
                onNavigate={(blade) => setActiveBlade(blade)}
                metrics={metrics}
                isOnline={isOnline}
              />
            )}

            {activeBlade === 'gateway' && (
              <GatewayBlade
                metrics={metrics}
                isOnline={isOnline}
                demoStatus={demoStatus}
              />
            )}

            {activeBlade === 'load-test' && (
              <LoadTestBlade
                status={demoStatus}
                onTriggerBurst={handleTriggerBurst}
                onTriggerRecover={handleTriggerRecover}
                isActionLoading={isActionLoading}
              />
            )}
          </main>
        </div>
      </div>

      {/* Toast Notification */}
      {feedbackToast && (
        <div className="fixed bottom-5 right-5 z-50 bg-[#1B1A19] dark:bg-[#252423] text-white text-xs px-4 py-2.5 rounded-sm border border-[#323130] shadow-azureElevated flex items-center gap-2.5 animate-in slide-in-from-bottom-2 fade-in duration-150">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{feedbackToast}</span>
          <button onClick={() => setFeedbackToast(null)} className="text-slate-400 hover:text-white ml-2">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};

export default App;
