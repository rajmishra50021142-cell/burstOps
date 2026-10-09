import React from 'react';
import { ChevronRight, Home, Layers, Cpu, BarChart3, DollarSign, Flame, FileText, HeartPulse } from 'lucide-react';
import { PortalBlade } from '../types';

interface AzureBreadcrumbProps {
  activeBlade: PortalBlade;
  onNavigate: (blade: PortalBlade) => void;
  routingMode?: number;
  isOnline?: boolean;
}

export const AzureBreadcrumb: React.FC<AzureBreadcrumbProps> = ({
  activeBlade,
  onNavigate,
  routingMode = 0,
  isOnline = true,
}) => {
  const getBladeMeta = () => {
    switch (activeBlade) {
      case 'home':
        return {
          title: 'Home',
          subtitle: 'Welcome to BurstOps Portal on Microsoft Azure',
          icon: Home,
          breadcrumbs: [{ label: 'Home', blade: 'home' as PortalBlade }],
        };
      case 'gateway':
        return {
          title: 'burstops-gateway',
          subtitle: 'Layer-7 Elastic Ingress Gateway (2 Replicas, Central India)',
          icon: Cpu,
          breadcrumbs: [
            { label: 'Home', blade: 'home' as PortalBlade },
            { label: 'All resources', blade: 'all-resources' as PortalBlade },
            { label: 'burstops-gateway', blade: 'gateway' as PortalBlade },
          ],
        };
      case 'metrics':
        return {
          title: 'Metrics | Azure Monitor',
          subtitle: 'Real-time telemetry, deflection ratio, and hysteresis thresholds',
          icon: BarChart3,
          breadcrumbs: [
            { label: 'Home', blade: 'home' as PortalBlade },
            { label: 'Monitor', blade: 'metrics' as PortalBlade },
            { label: 'Metrics', blade: 'metrics' as PortalBlade },
          ],
        };
      case 'cost':
        return {
          title: 'Cost analysis | FinOps',
          subtitle: 'Continuous baseline vs serverless deflection economics',
          icon: DollarSign,
          breadcrumbs: [
            { label: 'Home', blade: 'home' as PortalBlade },
            { label: 'Cost Management + Billing', blade: 'cost' as PortalBlade },
            { label: 'Cost analysis', blade: 'cost' as PortalBlade },
          ],
        };
      case 'load-test':
        return {
          title: 'Load Test & Traffic Simulator',
          subtitle: 'Interactive load injection, mathematical canaries, and live logs',
          icon: Flame,
          breadcrumbs: [
            { label: 'Home', blade: 'home' as PortalBlade },
            { label: 'Test Plans', blade: 'load-test' as PortalBlade },
            { label: 'Load Test Controller', blade: 'load-test' as PortalBlade },
          ],
        };
      case 'activity-log':
        return {
          title: 'Activity log',
          subtitle: 'Subscription-level events, mode transitions, and state history',
          icon: FileText,
          breadcrumbs: [
            { label: 'Home', blade: 'home' as PortalBlade },
            { label: 'Monitor', blade: 'metrics' as PortalBlade },
            { label: 'Activity log', blade: 'activity-log' as PortalBlade },
          ],
        };
      case 'service-health':
        return {
          title: 'Service Health',
          subtitle: 'Resource health matrix across Kubernetes, Functions, and Redis',
          icon: HeartPulse,
          breadcrumbs: [
            { label: 'Home', blade: 'home' as PortalBlade },
            { label: 'Service Health', blade: 'service-health' as PortalBlade },
          ],
        };
      case 'all-resources':
      default:
        return {
          title: 'All resources',
          subtitle: 'BurstOps Cloud Resource Group (Central India)',
          icon: Layers,
          breadcrumbs: [
            { label: 'Home', blade: 'home' as PortalBlade },
            { label: 'All resources', blade: 'all-resources' as PortalBlade },
          ],
        };
    }
  };

  const meta = getBladeMeta();
  const IconComponent = meta.icon;

  if (activeBlade === 'home') {
    return null; // Azure portal home page doesn't show standard breadcrumbs
  }

  return (
    <div className="bg-white dark:bg-[#1B1A19] border-b border-[#EDEBE9] dark:border-[#292827] px-4 sm:px-6 py-2.5">
      {/* Breadcrumb Path */}
      <nav className="flex items-center gap-1.5 text-xs text-[#605E5C] dark:text-[#A19F9D] mb-1.5">
        {meta.breadcrumbs.map((crumb, idx) => {
          const isLast = idx === meta.breadcrumbs.length - 1;
          return (
            <React.Fragment key={crumb.label}>
              {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />}
              {isLast ? (
                <span className="font-semibold text-[#323130] dark:text-white truncate">
                  {crumb.label}
                </span>
              ) : (
                <button
                  onClick={() => onNavigate(crumb.blade)}
                  className="hover:text-azure-600 dark:hover:text-azure-400 hover:underline truncate"
                >
                  {crumb.label}
                </button>
              )}
            </React.Fragment>
          );
        })}
      </nav>

      {/* Title & Resource Type Subtitle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-sm bg-azure-500/10 dark:bg-azure-500/20 text-azure-600 dark:text-azure-400 flex items-center justify-center shrink-0">
            <IconComponent className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-base sm:text-lg font-semibold text-[#323130] dark:text-white tracking-tight">
              {meta.title}
            </h1>
            <p className="text-xs text-[#605E5C] dark:text-[#A19F9D]">
              {meta.subtitle}
            </p>
          </div>
        </div>

        {/* Live Status indicator in header */}
        {activeBlade === 'gateway' && (
          <div className="flex items-center gap-2 self-start sm:self-auto text-xs">
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-slate-100 dark:bg-[#252423] border border-[#EDEBE9] dark:border-[#323130] font-medium">
              <span className={`w-2 h-2 rounded-full ${
                !isOnline ? 'bg-rose-500' :
                routingMode === 1 ? 'bg-amber-500 animate-pulse' : 'bg-emerald-500'
              }`} />
              <span className="text-[#323130] dark:text-white">
                {!isOnline ? 'Offline' : routingMode === 1 ? 'Burst Active (PI Control)' : 'Baseline Steady'}
              </span>
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
