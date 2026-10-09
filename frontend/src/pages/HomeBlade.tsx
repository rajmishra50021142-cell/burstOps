import React from 'react';
import {
  Cpu,
  Zap,
  BarChart3,
  DollarSign,
  Flame,
  LayoutDashboard,
  ArrowRight,
  Layers,
  Server,
  Database,
  Compass,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  FolderKanban,
  CreditCard,
  BookOpen,
} from 'lucide-react';
import { PortalBlade, ParsedGatewayMetrics } from '../types';
import { ArchitectureDiagram } from '../components/ArchitectureDiagram';

interface HomeBladeProps {
  onNavigate: (blade: PortalBlade) => void;
  metrics: ParsedGatewayMetrics | null;
  isOnline: boolean;
}

export const HomeBlade: React.FC<HomeBladeProps> = ({ onNavigate, metrics, isOnline }) => {
  const azureServices = [
    { title: 'Gateway', subtitle: 'Layer-7 Router', icon: Cpu, blade: 'gateway' as PortalBlade, color: 'text-azure-500 bg-azure-50 dark:bg-azure-950/50' },
    { title: 'Serverless Function', subtitle: 'Flex Consumption', icon: Zap, blade: 'gateway' as PortalBlade, color: 'text-purple-500 bg-purple-50 dark:bg-purple-950/50' },
    { title: 'Monitor', subtitle: 'Metrics & Charts', icon: BarChart3, blade: 'metrics' as PortalBlade, color: 'text-sky-500 bg-sky-50 dark:bg-sky-950/50' },
    { title: 'Cost Management', subtitle: 'FinOps Breakeven', icon: DollarSign, blade: 'cost' as PortalBlade, color: 'text-emerald-500 bg-emerald-50 dark:bg-emerald-950/50' },
    { title: 'Load Test', subtitle: 'Simulate Bursts', icon: Flame, blade: 'load-test' as PortalBlade, color: 'text-amber-500 bg-amber-50 dark:bg-amber-950/50' },
    { title: 'Grafana', subtitle: 'Dashboard 3000', icon: LayoutDashboard, isExternal: true, url: 'http://localhost:3000', color: 'text-orange-500 bg-orange-50 dark:bg-orange-950/50' },
    { title: 'All resources', subtitle: 'Cloud Catalog', icon: Layers, blade: 'all-resources' as PortalBlade, color: 'text-blue-500 bg-blue-50 dark:bg-blue-950/50' },
  ];

  const recentResources = [
    { name: 'burstops-gateway', type: 'Gateway (Layer-7)', status: isOnline ? (metrics?.routingMode === 1 ? 'Burst Active' : 'Running') : 'Offline', location: 'Central India', group: 'rg-burstops-centralindia', blade: 'gateway' as PortalBlade },
    { name: 'func-burstops-cvkzqc', type: 'Function App (Flex Consumption)', status: 'Ready (Scale to zero)', location: 'Central India', group: 'rg-burstops-centralindia', blade: 'gateway' as PortalBlade },
    { name: 'dummy-backend-sieve', type: 'Kubernetes Deployment (AKS)', status: 'Running (2 replicas)', location: 'Central India', group: 'rg-burstops-centralindia', blade: 'gateway' as PortalBlade },
    { name: 'burstops-redis-cache', type: 'Redis Distributed Backplane', status: metrics?.redisUp ? 'Connected' : 'Offline', location: 'Central India', group: 'rg-burstops-centralindia', blade: 'service-health' as PortalBlade },
    { name: 'prometheus-k8s', type: 'Monitoring Workspace', status: 'Scraping (2s interval)', location: 'Central India', group: 'rg-burstops-centralindia', blade: 'metrics' as PortalBlade },
    { name: 'grafana-telemetry-portal', type: 'Dashboard Workspace', status: 'Ready (Port 3000)', location: 'Central India', group: 'rg-burstops-centralindia', isExternal: true, url: 'http://localhost:3000' },
  ];

  const tools = [
    { name: 'Grafana Telemetry', port: 'Port 3000', desc: 'Prometheus metrics visualizer with prebuilt BurstOps dashboard panels.', url: 'http://localhost:3000', icon: LayoutDashboard, badge: 'Recommended' },
    { name: 'Jaeger Distributed Tracing', port: 'Port 16686', desc: 'End-to-end distributed span traces through gateway, k8s, and serverless.', url: 'http://localhost:16686', icon: ActivityIcon, badge: 'Tracing' },
    { name: 'Locust Load Generator', port: 'Port 8089', desc: 'Interactive traffic injector to simulate user swarms and stress tests.', url: 'http://localhost:8089', icon: Flame, badge: 'Load Test' },
    { name: 'Prometheus Raw Metrics', port: 'Port 9090', desc: 'PromQL interface to inspect scraped telemetry counters directly.', url: 'http://localhost:9090', icon: BarChart3, badge: 'Metrics' },
  ];

  function ActivityIcon(props: any) {
    return <Compass {...props} />;
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto select-none">
      {/* Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-[#EDEBE9] dark:border-[#292827]">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold text-[#323130] dark:text-white tracking-tight">
            Azure services
          </h1>
          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D]">
            Manage, observe, and simulate cloud traffic for BurstOps elastic burst gateway.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs px-2.5 py-1 rounded-sm bg-azure-50 dark:bg-azure-950 text-azure-700 dark:text-azure-300 font-semibold border border-azure-200 dark:border-azure-800">
            Subscription: Azure Student / Enterprise
          </span>
        </div>
      </div>

      {/* Azure Services Row (Large Icon Tiles) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-3">
        {azureServices.map((service) => {
          const Icon = service.icon;
          if (service.isExternal) {
            return (
              <a
                key={service.title}
                href={service.url}
                target="_blank"
                rel="noopener noreferrer"
                className="azure-card p-3 rounded-sm flex flex-col items-center justify-center text-center hover:shadow-azureElevated hover:border-azure-400 transition-all group"
              >
                <div className={`w-10 h-10 rounded-sm flex items-center justify-center mb-2 ${service.color}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <span className="text-xs font-semibold text-[#323130] dark:text-white group-hover:text-azure-500 transition-colors">
                  {service.title}
                </span>
                <span className="text-[10px] text-[#605E5C] dark:text-[#A19F9D] mt-0.5">
                  {service.subtitle}
                </span>
              </a>
            );
          }

          return (
            <button
              key={service.title}
              onClick={() => service.blade && onNavigate(service.blade)}
              className="azure-card p-3 rounded-sm flex flex-col items-center justify-center text-center hover:shadow-azureElevated hover:border-azure-400 transition-all group cursor-pointer"
            >
              <div className={`w-10 h-10 rounded-sm flex items-center justify-center mb-2 ${service.color}`}>
                <Icon className="w-5 h-5" />
              </div>
              <span className="text-xs font-semibold text-[#323130] dark:text-white group-hover:text-azure-500 transition-colors">
                {service.title}
              </span>
              <span className="text-[10px] text-[#605E5C] dark:text-[#A19F9D] mt-0.5">
                {service.subtitle}
              </span>
            </button>
          );
        })}
      </div>

      {/* Recent Resources Table */}
      <div className="azure-card rounded-sm overflow-hidden">
        <div className="px-4 py-3 bg-[#FAF9F8] dark:bg-[#1B1A19] border-b border-[#EDEBE9] dark:border-[#292827] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-azure-500" />
            <h2 className="font-semibold text-xs text-[#323130] dark:text-white">Recent resources</h2>
          </div>
          <button
            onClick={() => onNavigate('all-resources')}
            className="text-xs text-azure-600 dark:text-azure-400 hover:underline flex items-center gap-1"
          >
            See all resources →
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full azure-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Status</th>
                <th>Location</th>
                <th>Resource group</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {recentResources.map((res) => (
                <tr key={res.name} className="transition-colors">
                  <td className="font-semibold text-azure-600 dark:text-azure-400">
                    {res.isExternal ? (
                      <a href={res.url} target="_blank" rel="noopener noreferrer" className="hover:underline flex items-center gap-1.5">
                        <span>{res.name}</span>
                        <ExternalLink className="w-3 h-3 text-slate-400" />
                      </a>
                    ) : (
                      <button onClick={() => res.blade && onNavigate(res.blade)} className="hover:underline text-left">
                        {res.name}
                      </button>
                    )}
                  </td>
                  <td className="text-[#605E5C] dark:text-[#A19F9D] font-mono text-[11px]">{res.type}</td>
                  <td>
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] bg-slate-100 dark:bg-black/30 text-[#323130] dark:text-[#F3F2F1]">
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        res.status.includes('Burst') ? 'bg-amber-500' :
                        res.status.includes('Running') || res.status.includes('Ready') || res.status.includes('Connected') || res.status.includes('Scraping')
                          ? 'bg-emerald-500'
                          : 'bg-rose-500'
                      }`} />
                      {res.status}
                    </span>
                  </td>
                  <td className="text-[#605E5C] dark:text-[#A19F9D]">{res.location}</td>
                  <td className="text-azure-600 dark:text-azure-400 hover:underline cursor-pointer">{res.group}</td>
                  <td>
                    {res.isExternal ? (
                      <a href={res.url} target="_blank" rel="noopener noreferrer" className="text-azure-600 dark:text-azure-400 text-xs font-semibold hover:underline">
                        Open
                      </a>
                    ) : (
                      <button onClick={() => res.blade && onNavigate(res.blade)} className="text-azure-600 dark:text-azure-400 text-xs font-semibold hover:underline">
                        Manage
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Navigate Cards Row (Subscriptions & Resource Groups) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div
          onClick={() => onNavigate('gateway')}
          className="azure-card p-4 rounded-sm hover:border-azure-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center gap-2 mb-2">
            <CreditCard className="w-4 h-4 text-azure-500" />
            <h3 className="font-semibold text-xs text-[#323130] dark:text-white">Subscriptions</h3>
          </div>
          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D] leading-relaxed">
            Azure Student / Enterprise active subscription. Includes AKS cluster and Flex Consumption Azure Functions.
          </p>
          <div className="mt-3 text-xs text-azure-600 dark:text-azure-400 font-semibold flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            <span>View gateway billing</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </div>

        <div
          onClick={() => onNavigate('all-resources')}
          className="azure-card p-4 rounded-sm hover:border-azure-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center gap-2 mb-2">
            <FolderKanban className="w-4 h-4 text-azure-500" />
            <h3 className="font-semibold text-xs text-[#323130] dark:text-white">Resource Groups</h3>
          </div>
          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D] leading-relaxed">
            <code>rg-burstops-centralindia</code> contains gateway instances, AKS pods, Redis state cache, and Azure Function.
          </p>
          <div className="mt-3 text-xs text-azure-600 dark:text-azure-400 font-semibold flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            <span>Explore resource group</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </div>

        <div
          onClick={() => onNavigate('metrics')}
          className="azure-card p-4 rounded-sm hover:border-azure-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center gap-2 mb-2">
            <BarChart3 className="w-4 h-4 text-azure-500" />
            <h3 className="font-semibold text-xs text-[#323130] dark:text-white">Azure Monitor</h3>
          </div>
          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D] leading-relaxed">
            Live telemetry charts: observed CPU % against 80% burst and 60% recovery hysteresis setpoints.
          </p>
          <div className="mt-3 text-xs text-azure-600 dark:text-azure-400 font-semibold flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            <span>Launch metrics explorer</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </div>
      </div>

      {/* Tools Row (Grafana, Jaeger, Locust, Prometheus) */}
      <div className="space-y-3">
        <h2 className="font-semibold text-xs text-[#323130] dark:text-white flex items-center gap-2">
          <Compass className="w-4 h-4 text-azure-500" />
          <span>Integrated Telemetry & Load Tools</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {tools.map((t) => {
            const Icon = t.icon;
            return (
              <a
                key={t.name}
                href={t.url}
                target="_blank"
                rel="noopener noreferrer"
                className="azure-card p-3.5 rounded-sm hover:border-azure-400 transition-all group flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-1 mb-1.5">
                    <div className="flex items-center gap-1.5 font-semibold text-xs text-[#323130] dark:text-white group-hover:text-azure-500 transition-colors">
                      <Icon className="w-4 h-4 text-azure-500" />
                      <span>{t.name}</span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-black/30 px-1.5 py-0.5 rounded">
                      {t.port}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] leading-relaxed">
                    {t.desc}
                  </p>
                </div>
                <div className="mt-3 pt-2 border-t border-[#EDEBE9] dark:border-[#292827] flex items-center justify-between text-xs text-azure-600 dark:text-azure-400 font-semibold">
                  <span>Open Tool</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </div>
              </a>
            );
          })}
        </div>
      </div>

      {/* Architecture Overview Section */}
      <div className="pt-2">
        <ArchitectureDiagram />
      </div>
    </div>
  );
};
