import React from 'react';
import {
  Home,
  LayoutDashboard,
  Layers,
  Cpu,
  BarChart3,
  DollarSign,
  Flame,
  FileText,
  HeartPulse,
  Plus,
  Compass,
  ChevronRight,
} from 'lucide-react';
import { PortalBlade } from '../types';

interface AzureSidebarProps {
  isOpen: boolean;
  activeBlade: PortalBlade;
  onNavigate: (blade: PortalBlade) => void;
  onOpenCreateResource: () => void;
}

export const AzureSidebar: React.FC<AzureSidebarProps> = ({
  isOpen,
  activeBlade,
  onNavigate,
  onOpenCreateResource,
}) => {
  const navItems = [
    { blade: 'home' as PortalBlade, label: 'Home', icon: Home },
    { blade: 'dashboard' as any, label: 'Dashboard', icon: LayoutDashboard, targetBlade: 'gateway' as PortalBlade },
    { blade: 'all-resources' as PortalBlade, label: 'All resources', icon: Layers },
  ];

  const favorites = [
    { blade: 'gateway' as PortalBlade, label: 'Gateway (Layer-7)', icon: Cpu, badge: 'Core' },
    { blade: 'metrics' as PortalBlade, label: 'Monitor (Metrics)', icon: BarChart3 },
    { blade: 'cost' as PortalBlade, label: 'Cost Management', icon: DollarSign, badge: 'FinOps' },
    { blade: 'load-test' as PortalBlade, label: 'Load Test & Simulator', icon: Flame },
    { blade: 'activity-log' as PortalBlade, label: 'Activity log', icon: FileText },
    { blade: 'service-health' as PortalBlade, label: 'Service health', icon: HeartPulse },
  ];

  return (
    <aside
      className={`fixed top-12 bottom-0 left-0 z-40 bg-white dark:bg-[#1B1A19] border-r border-[#EDEBE9] dark:border-[#292827] transition-all duration-200 select-none flex flex-col justify-between overflow-y-auto ${
        isOpen ? 'w-56' : 'w-12'
      }`}
    >
      <div>
        {/* Create a resource button */}
        <div className="p-2 border-b border-[#EDEBE9] dark:border-[#292827]">
          <button
            onClick={onOpenCreateResource}
            className={`w-full h-8 flex items-center rounded-sm text-xs font-semibold transition-colors ${
              isOpen
                ? 'px-2.5 gap-2 bg-azure-500 hover:bg-azure-600 text-white shadow-xs'
                : 'justify-center text-azure-500 hover:bg-azure-50 dark:hover:bg-azure-950/40'
            }`}
            title="Create a resource"
          >
            <Plus className="w-4 h-4 shrink-0" />
            {isOpen && <span>Create a resource</span>}
          </button>
        </div>

        {/* Primary Navigation */}
        <nav className="py-2 space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const target = item.targetBlade || item.blade;
            const isActive = activeBlade === target;
            return (
              <button
                key={item.label}
                onClick={() => onNavigate(target)}
                className={`w-full h-9 flex items-center px-3.5 text-xs transition-colors relative ${
                  isActive
                    ? 'text-azure-600 dark:text-azure-400 font-semibold bg-azure-50/70 dark:bg-azure-950/30'
                    : 'text-[#323130] dark:text-[#F3F2F1] hover:bg-[#F3F2F1] dark:hover:bg-[#252423]'
                }`}
                title={!isOpen ? item.label : undefined}
              >
                {isActive && (
                  <div className="absolute left-0 top-0 bottom-0 w-1 bg-azure-500 rounded-r-sm"></div>
                )}
                <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-azure-500' : 'text-[#605E5C] dark:text-[#A19F9D]'}`} />
                {isOpen && <span className="ml-3 truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>

        {/* Favorites Section */}
        <div className="pt-2">
          {isOpen ? (
            <div className="px-3.5 py-1.5 text-[11px] font-semibold text-[#605E5C] dark:text-[#A19F9D] uppercase tracking-wider">
              Favorites
            </div>
          ) : (
            <div className="w-6 mx-auto my-1 border-t border-[#EDEBE9] dark:border-[#292827]" />
          )}

          <div className="space-y-0.5">
            {favorites.map((item) => {
              const Icon = item.icon;
              const isActive = activeBlade === item.blade;
              return (
                <button
                  key={item.blade}
                  onClick={() => onNavigate(item.blade)}
                  className={`w-full h-9 flex items-center px-3.5 text-xs transition-colors relative justify-between ${
                    isActive
                      ? 'text-azure-600 dark:text-azure-400 font-semibold bg-azure-50/70 dark:bg-azure-950/30'
                      : 'text-[#323130] dark:text-[#F3F2F1] hover:bg-[#F3F2F1] dark:hover:bg-[#252423]'
                  }`}
                  title={!isOpen ? item.label : undefined}
                >
                  {isActive && (
                    <div className="absolute left-0 top-0 bottom-0 w-1 bg-azure-500 rounded-r-sm"></div>
                  )}
                  <div className="flex items-center">
                    <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-azure-500' : 'text-[#605E5C] dark:text-[#A19F9D]'}`} />
                    {isOpen && <span className="ml-3 truncate">{item.label}</span>}
                  </div>
                  {isOpen && item.badge && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-azure-100 dark:bg-azure-950 text-azure-700 dark:text-azure-300">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Sidebar Footer */}
      {isOpen && (
        <div className="p-3 border-t border-[#EDEBE9] dark:border-[#292827] text-[11px] text-[#605E5C] dark:text-[#A19F9D] flex items-center justify-between">
          <span>Azure Central India</span>
          <span className="text-azure-500 font-medium">v1.35.8</span>
        </div>
      )}
    </aside>
  );
};
