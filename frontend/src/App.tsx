import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AzureTopBar } from './components/AzureTopBar';
import { AzureSidebar } from './components/AzureSidebar';
import { AzureBreadcrumb } from './components/AzureBreadcrumb';
import { AzureCommandBar } from './components/AzureCommandBar';

import { HomeBlade } from './pages/HomeBlade';
import { GatewayBlade } from './pages/GatewayBlade';
import { MetricsBlade } from './pages/MetricsBlade';
import { CostBlade } from './pages/CostBlade';
import { LoadTestBlade } from './pages/LoadTestBlade';
import { ActivityLogBlade } from './pages/ActivityLogBlade';
import { ServiceHealthBlade } from './pages/ServiceHealthBlade';
import { AllResourcesBlade } from './pages/AllResourcesBlade';

import { fetchDemoStatus, triggerBurst, triggerRecovery } from './api';
import { useMetricsHistory } from './hooks/useMetricsHistory';
import { getGatewayBaseUrl, setGatewayBaseUrl } from './lib/gatewayApi';
import { PortalBlade, DemoStatusResponse, LogEntry } from './types';
import { AlertCircle, CheckCircle2, X } from 'lucide-react';

export const App: React.FC = () => {
  // Navigation & UI State
  const [activeBlade, setActiveBlade] = useState<PortalBlade>('home');
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [gatewayUrl, setGatewayUrlState] = useState<string>(getGatewayBaseUrl());
  const [feedbackToast, setFeedbackToast] = useState<string | null>(null);

  // Existing Demo State & API Polling
  const [demoStatus, setDemoStatus] = useState<DemoStatusResponse | null>(null);
  const [isActionLoading, setIsActionLoading] = useState<boolean>(false);
  const [demoErrorMessage, setDemoErrorMessage] = useState<string | null>(null);
  const isDemoPollingRef = useRef<boolean>(false);

  // Gateway Prometheus Metrics & Telemetry History Hook
  const {
    metrics,
    history,
    isOnline,
    notifications,
    activityLogs,
    poll: pollMetrics,
    markAllNotificationsRead,
  } = useMetricsHistory();

  // Initialize theme from localStorage or document
  useEffect(() => {
    const savedTheme = (localStorage.getItem('burstops_portal_theme') as 'dark' | 'light') || 'dark';
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

  const handleSaveGatewayUrl = (url: string) => {
    setGatewayBaseUrl(url);
    setGatewayUrlState(getGatewayBaseUrl());
    pollMetrics();
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
    setFeedbackToast('Blade telemetry refreshed');
  };

  // Auto-dismiss toast
  useEffect(() => {
    if (feedbackToast) {
      const timer = setTimeout(() => setFeedbackToast(null), 3500);
      return () => clearTimeout(timer);
    }
  }, [feedbackToast]);

  // Determine logs to display for console
  const activeRun = demoStatus?.current_run || demoStatus?.last_completed_run;
  const logs: LogEntry[] = activeRun?.logs || [];
  const activeRunId = activeRun?.run_id || null;

  return (
    <div className="min-h-screen flex flex-col bg-[#FAF9F8] dark:bg-[#11100F] text-[#323130] dark:text-[#F3F2F1]">
      {/* 1. Azure Portal Top Bar (48px) - NO top-right badges from Image 2! */}
      <AzureTopBar
        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        activeBlade={activeBlade}
        onNavigate={(blade) => setActiveBlade(blade)}
        isOnline={isOnline}
        routingMode={metrics?.routingMode ?? 0}
        cpuPercent={metrics?.cpuObservedPercent ?? 0}
        notifications={notifications}
        onMarkNotificationsRead={markAllNotificationsRead}
        theme={theme}
        onToggleTheme={handleToggleTheme}
        gatewayUrl={gatewayUrl}
        onSaveGatewayUrl={handleSaveGatewayUrl}
      />

      {/* Main Layout Container */}
      <div className="flex-1 flex relative">
        {/* 2. Azure Left Collapsible Rail */}
        <AzureSidebar
          isOpen={isSidebarOpen}
          activeBlade={activeBlade}
          onNavigate={(blade) => setActiveBlade(blade)}
          onOpenCreateResource={() => setActiveBlade('load-test')}
        />

        {/* Content Area offset by sidebar */}
        <div
          className={`flex-1 flex flex-col transition-all duration-200 min-w-0 ${
            isSidebarOpen ? 'ml-56' : 'ml-12'
          }`}
        >
          {/* 3. Azure Breadcrumb & Blade Title */}
          <AzureBreadcrumb
            activeBlade={activeBlade}
            onNavigate={(blade) => setActiveBlade(blade)}
            routingMode={metrics?.routingMode ?? 0}
            isOnline={isOnline}
          />

          {/* 4. Azure Command Bar (Toolbar) */}
          <AzureCommandBar
            onRefresh={handleRefreshAll}
            onTriggerBurst={handleTriggerBurst}
            onTriggerRecover={handleTriggerRecover}
            isActionLoading={isActionLoading}
            demoStatus={demoStatus}
            onShowFeedbackToast={() => setFeedbackToast('Feedback submitted to BurstOps Portal team')}
          />

          {/* Error Banner if Demo Controller is offline */}
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

          {/* 5. Blade Pages View */}
          <main className="flex-1 pb-12">
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
                history={history}
                isOnline={isOnline}
                demoStatus={demoStatus}
                onNavigateToMetrics={() => setActiveBlade('metrics')}
                onNavigateToLoadTest={() => setActiveBlade('load-test')}
              />
            )}

            {activeBlade === 'metrics' && (
              <MetricsBlade
                metrics={metrics}
                history={history}
                onRefresh={pollMetrics}
              />
            )}

            {activeBlade === 'cost' && (
              <CostBlade metrics={metrics} />
            )}

            {activeBlade === 'load-test' && (
              <LoadTestBlade
                status={demoStatus}
                onTriggerBurst={handleTriggerBurst}
                onTriggerRecover={handleTriggerRecover}
                isActionLoading={isActionLoading}
                logs={logs}
                activeRunId={activeRunId}
              />
            )}

            {activeBlade === 'activity-log' && (
              <ActivityLogBlade
                logs={activityLogs}
                onRefresh={pollMetrics}
              />
            )}

            {activeBlade === 'service-health' && (
              <ServiceHealthBlade
                metrics={metrics}
                isOnline={isOnline}
                onRefresh={handleRefreshAll}
              />
            )}

            {activeBlade === 'all-resources' && (
              <AllResourcesBlade
                onNavigate={(blade) => setActiveBlade(blade)}
                isOnline={isOnline}
              />
            )}
          </main>
        </div>
      </div>

      {/* Floating Toast Notification */}
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
