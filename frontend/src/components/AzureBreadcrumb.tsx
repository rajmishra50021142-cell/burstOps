import React from 'react';
import { ChevronRight, Home, Cpu, Flame } from 'lucide-react';
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
      case 'gateway':
        return {
          title: 'Gateway',
          subtitle: 'Layer-7 Elastic Ingress Gateway (2 Replicas, Central India)',
          icon: Cpu,
          breadcrumbs: [
            { label: 'Home', blade: 'home' as PortalBlade },
            { label: 'Gateway', blade: 'gateway' as PortalBlade },
          ],
        };
      case 'load-test':
        return {
          title: 'Load Test & Simulator',
          subtitle: 'Interactive load injection, mathematical canaries, and live verification',
          icon: Flame,
          breadcrumbs: [
            { label: 'Home', blade: 'home' as PortalBlade },
            { label: 'Load Test & Simulator', blade: 'load-test' as PortalBlade },
          ],
        };
      case 'home':
      default:
        return {
          title: 'Home',
          subtitle: 'Welcome to BurstOps Portal on Microsoft Azure',
          icon: Home,
          breadcrumbs: [{ label: 'Home', blade: 'home' as PortalBlade }],
        };
    }
  };

  const meta = getBladeMeta();
  const IconComponent = meta.icon;

  if (activeBlade === 'home') {
    return null;
  }

  return (
    <div className="bg-white dark:bg-[#1B1A19] border-b border-[#EDEBE9] dark:border-[#292827] px-4 sm:px-6 py-2.5 select-none">
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
              <span
                className={`w-2 h-2 rounded-full ${
                  !isOnline ? 'bg-rose-500' : routingMode === 1 ? 'bg-amber-500 animate-pulse' : 'bg-emerald-500'
                }`}
              />
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
