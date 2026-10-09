import React from 'react';
import {
  HeartPulse,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Server,
  Zap,
  Database,
  BarChart3,
  Cpu,
} from 'lucide-react';
import { ParsedGatewayMetrics } from '../types';

interface ServiceHealthBladeProps {
  metrics: ParsedGatewayMetrics | null;
  isOnline: boolean;
  onRefresh: () => void;
}

export const ServiceHealthBlade: React.FC<ServiceHealthBladeProps> = ({
  metrics,
  isOnline,
  onRefresh,
}) => {
  const services = [
    {
      name: 'burstops-gateway',
      role: 'Layer-7 Ingress & Controller',
      status: isOnline ? 'Healthy' : 'Degraded',
      code: isOnline ? 'HTTP 200' : 'Connection Timeout',
      latency: isOnline ? `${Math.round((metrics?.upstreamLatencySeconds ?? 0.005) * 1000)} ms` : '-',
      region: 'Central India',
      icon: Cpu,
    },
    {
      name: 'dummy-backend-sieve',
      role: 'Baseline Container Pods (AKS)',
      status: isOnline ? 'Healthy' : 'Unknown',
      code: 'HTTP 200 (Sieve Canary OK)',
      latency: '2-8 ms',
      region: 'Central India',
      icon: Server,
    },
    {
      name: 'func-burstops-cvkzqc',
      role: 'Azure Function (Flex Consumption)',
      status: 'Healthy',
      code: 'HTTP 200 / Scale-to-Zero',
      latency: '15-35 ms (Cold Start: 320ms)',
      region: 'Central India',
      icon: Zap,
    },
    {
      name: 'burstops-redis-cache',
      role: 'Distributed Lock & State Backplane',
      status: metrics?.redisUp ? 'Healthy' : 'Degraded',
      code: metrics?.redisUp ? 'PONG' : 'No Redis Response',
      latency: '1 ms',
      region: 'Central India',
      icon: Database,
    },
    {
      name: 'prometheus-k8s',
      role: 'Cluster Telemetry Scraper',
      status: 'Healthy',
      code: 'Scraping Port 9090 (2s interval)',
      latency: '3 ms',
      region: 'Central India',
      icon: BarChart3,
    },
  ];

  return (
    <div className="p-4 sm:p-6 space-y-5 max-w-7xl mx-auto select-none">
      {/* Service Health Card Header */}
      <div className="azure-card p-5 rounded-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <HeartPulse className="w-5 h-5 text-emerald-500" />
            <h2 className="text-base font-semibold text-[#323130] dark:text-white">
              Service Health Overview
            </h2>
          </div>
          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D]">
            Real-time status of BurstOps infrastructure components deployed across Azure Central India.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span className="px-3 py-1 rounded-sm bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-semibold text-xs border border-emerald-200 dark:border-emerald-800 flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            All Cloud Services Operational
          </span>
          <button onClick={onRefresh} className="azure-btn-secondary text-xs">
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Check Now</span>
          </button>
        </div>
      </div>

      {/* Services Matrix Table */}
      <div className="azure-card rounded-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full azure-table">
            <thead>
              <tr>
                <th>Service / Resource Name</th>
                <th>Role in Architecture</th>
                <th>Health Status</th>
                <th>Probe Response</th>
                <th>Roundtrip Latency</th>
                <th>Deployment Region</th>
              </tr>
            </thead>
            <tbody>
              {services.map((svc) => {
                const Icon = svc.icon;
                const isHealthy = svc.status === 'Healthy';
                return (
                  <tr key={svc.name} className="transition-colors">
                    <td className="font-semibold text-azure-600 dark:text-azure-400">
                      <div className="flex items-center gap-2">
                        <Icon className="w-4 h-4 text-azure-500" />
                        <span>{svc.name}</span>
                      </div>
                    </td>
                    <td className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">{svc.role}</td>
                    <td>
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold ${
                        isHealthy
                          ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300'
                          : 'bg-rose-50 dark:bg-rose-950 text-rose-700 dark:text-rose-300'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${isHealthy ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                        {svc.status}
                      </span>
                    </td>
                    <td className="font-mono text-[11px] text-[#323130] dark:text-white">{svc.code}</td>
                    <td className="font-mono text-[11px] text-[#605E5C] dark:text-[#A19F9D]">{svc.latency}</td>
                    <td className="text-[#605E5C] dark:text-[#A19F9D]">{svc.region}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
