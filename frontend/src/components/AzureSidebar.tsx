import React from 'react';
import { Home, Cpu, Flame } from 'lucide-react';
import { PortalBlade } from '../types';

interface AzureSidebarProps {
  isOpen: boolean;
  activeBlade: PortalBlade;
  onNavigate: (blade: PortalBlade) => void;
}

export const AzureSidebar: React.FC<AzureSidebarProps> = ({
  isOpen,
  activeBlade,
  onNavigate,
}) => {
  const items = [
    { blade: 'home' as PortalBlade, label: 'Home', icon: Home },
    { blade: 'gateway' as PortalBlade, label: 'Gateway', icon: Cpu },
    { blade: 'load-test' as PortalBlade, label: 'Load Test & Simulator', icon: Flame },
  ];

  return (
    <aside
      className={`fixed top-12 bottom-0 left-0 z-40 bg-white dark:bg-[#1B1A19] border-r border-[#EDEBE9] dark:border-[#292827] transition-all duration-200 select-none flex flex-col justify-between overflow-y-auto ${
        isOpen ? 'w-56' : 'w-12'
      }`}
    >
      <nav className="py-2 space-y-0.5">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = activeBlade === item.blade;
          return (
            <button
              key={item.label}
              onClick={() => onNavigate(item.blade)}
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
              <Icon
                className={`w-4 h-4 shrink-0 ${
                  isActive ? 'text-azure-500' : 'text-[#605E5C] dark:text-[#A19F9D]'
                }`}
              />
              {isOpen && <span className="ml-3 truncate">{item.label}</span>}
            </button>
          );
        })}
      </nav>

      {isOpen && (
        <div className="p-3 border-t border-[#EDEBE9] dark:border-[#292827] text-[11px] text-[#605E5C] dark:text-[#A19F9D] flex items-center justify-between">
          <span>Azure Central India</span>
          <span className="text-azure-500 font-medium">v1.35.8</span>
        </div>
      )}
    </aside>
  );
};
