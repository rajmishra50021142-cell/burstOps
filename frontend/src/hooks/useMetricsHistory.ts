import { useState, useEffect, useRef, useCallback } from 'react';
import { ParsedGatewayMetrics, MetricHistoryPoint, ActivityLogItem, PortalNotification } from '../types';
import { fetchGatewayMetrics } from '../lib/gatewayApi';

export function useMetricsHistory() {
  const [metrics, setMetrics] = useState<ParsedGatewayMetrics | null>(null);
  const [history, setHistory] = useState<MetricHistoryPoint[]>([]);
  const [isOnline, setIsOnline] = useState<boolean>(true);
  const [notifications, setNotifications] = useState<PortalNotification[]>([
    {
      id: 'init-1',
      type: 'info',
      title: 'BurstOps Portal Initialized',
      message: 'Connected to Microsoft Azure Central India environment. Monitoring Layer-7 gateway.',
      timestamp: Date.now(),
      read: false,
    },
  ]);
  const [activityLogs, setActivityLogs] = useState<ActivityLogItem[]>([
    {
      id: 'act-init',
      timestamp: new Date().toLocaleTimeString(),
      operationName: 'Gateway Initialization',
      status: 'Succeeded',
      initiatedBy: 'BurstOps Controller',
      resource: 'burstops-gateway-centralindia',
      cpuPercent: 24.5,
      details: 'Gateway poller listening. Hysteresis thresholds locked at 80% burst / 60% recovery.',
    },
  ]);

  const prevMetricsRef = useRef<ParsedGatewayMetrics | null>(null);
  const prevModeRef = useRef<number | null>(null);
  const isPollingRef = useRef<boolean>(false);

  const addNotification = useCallback((n: Omit<PortalNotification, 'id' | 'timestamp'>) => {
    setNotifications((prev) => [
      {
        ...n,
        id: `notif-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
        timestamp: Date.now(),
        read: false,
      },
      ...prev.slice(0, 49),
    ]);
  }, []);

  const addActivityLog = useCallback((item: Omit<ActivityLogItem, 'id'>) => {
    setActivityLogs((prev) => [
      {
        ...item,
        id: `act-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      },
      ...prev.slice(0, 99),
    ]);
  }, []);

  const poll = useCallback(async () => {
    if (isPollingRef.current) return;
    isPollingRef.current = true;

    try {
      const current = await fetchGatewayMetrics();
      setIsOnline(true);
      setMetrics(current);

      const prev = prevMetricsRef.current;
      const now = Date.now();
      const timeLabel = new Date(now).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

      // Compute incremental RPS if previous point exists
      let k8sRps = 0;
      let serverlessRps = 0;
      if (prev) {
        const deltaSec = Math.max(0.5, (now - prev.timestamp) / 1000);
        const deltaK8s = Math.max(0, current.requestsRoutedK8s - prev.requestsRoutedK8s);
        const deltaSls = Math.max(0, current.requestsRoutedServerless - prev.requestsRoutedServerless);
        k8sRps = Math.round((deltaK8s / deltaSec) * 10) / 10;
        serverlessRps = Math.round((deltaSls / deltaSec) * 10) / 10;
      }

      const point: MetricHistoryPoint = {
        timestamp: now,
        timeLabel,
        cpuPercent: current.cpuObservedPercent,
        deflectRatio: current.deflectRatio,
        k8sRps,
        serverlessRps,
        totalRps: Math.round((k8sRps + serverlessRps) * 10) / 10,
        latencyMs: Math.round(current.upstreamLatencySeconds * 1000),
        routingMode: current.routingMode,
      };

      setHistory((prevHistory) => {
        const next = [...prevHistory, point];
        // Keep max 150 points (~5 minutes at 2s interval)
        return next.length > 150 ? next.slice(next.length - 150) : next;
      });

      // Detect routing mode transitions
      if (prevModeRef.current !== null && prevModeRef.current !== current.routingMode) {
        if (current.routingMode === 1) {
          addNotification({
            type: 'warning',
            title: 'Burst Deflection Activated',
            message: `Observed CPU reached ${current.cpuObservedPercent}%. Gateway engaged PI deflection to Azure Functions.`,
          });
          addActivityLog({
            timestamp: timeLabel,
            operationName: 'Burst Deflection Initiated',
            status: 'Succeeded',
            initiatedBy: 'PI Controller',
            resource: 'burstops-gateway-centralindia',
            cpuPercent: current.cpuObservedPercent,
            details: `Threshold >= 80% crossed. Deflection ratio climbing to ${Math.round(current.deflectRatio * 100)}%. Overflow sent to serverless.`,
          });
        } else {
          addNotification({
            type: 'success',
            title: 'Recovered to Baseline',
            message: `Observed CPU dropped to ${current.cpuObservedPercent}%. Traffic safely returned 100% to Kubernetes pods.`,
          });
          addActivityLog({
            timestamp: timeLabel,
            operationName: 'Baseline Recovery Completed',
            status: 'Succeeded',
            initiatedBy: 'PI Controller',
            resource: 'burstops-gateway-centralindia',
            cpuPercent: current.cpuObservedPercent,
            details: `Cooldown < 60% reached. Deflection ratio zeroed. Routing 100% to AKS pods.`,
          });
        }
      }

      prevModeRef.current = current.routingMode;
      prevMetricsRef.current = current;
    } catch {
      // Graceful offline state
      setIsOnline(false);
      // Keep last metrics or synthesized standby metrics so charts don't crash
    } finally {
      isPollingRef.current = false;
    }
  }, [addNotification, addActivityLog]);

  useEffect(() => {
    poll();
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, [poll]);

  const markAllNotificationsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  return {
    metrics,
    history,
    isOnline,
    notifications,
    activityLogs,
    poll,
    addNotification,
    addActivityLog,
    markAllNotificationsRead,
  };
}
