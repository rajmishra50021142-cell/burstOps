import React from 'react';
import { Menu, Sun, Moon } from 'lucide-react';
import { PortalBlade } from '../types';

interface AzureTopBarProps {
  onToggleSidebar: () => void;
  onNavigate: (blade: PortalBlade) => void;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
}

export const AzureTopBar: React.FC<AzureTopBarProps> = ({
  onToggleSidebar,
  onNavigate,
  theme,
  onToggleTheme,
}) => {
  return (
    <header className="h-12 bg-[#001833] dark:bg-[#11100F] border-b border-[#002447] dark:border-[#292827] text-white flex items-center justify-between px-3 z-50 select-none sticky top-0">
      {/* Left: Hamburger & Portal Branding */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="w-8 h-8 flex items-center justify-center hover:bg-white/10 active:bg-white/15 rounded-sm transition-colors text-white"
          title="Toggle sidebar"
          aria-label="Toggle navigation"
        >
          <Menu className="w-4 h-4" />
        </button>

        {/* BurstOps Portal Logo */}
        <button
          onClick={() => onNavigate('home')}
          className="flex items-center gap-2 group text-left focus:outline-none"
        >
          <div className="w-6 h-6 rounded-sm bg-gradient-to-br from-[#0078D4] via-[#005A9E] to-[#004578] flex items-center justify-center shadow-sm">
            <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4 text-white" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <span className="font-semibold text-[14px] tracking-tight text-white group-hover:text-azure-300 transition-colors">
            BurstOps Portal
          </span>
        </button>
      </div>

      {/* Right: Unobtrusive Theme Toggle */}
      <div className="flex items-center">
        <button
          onClick={onToggleTheme}
          className="w-8 h-8 flex items-center justify-center hover:bg-white/10 rounded-sm text-slate-300 hover:text-white transition-colors"
          title={theme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme'}
          aria-label="Toggle Theme"
        >
          {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-sky-300" />}
        </button>
      </div>
    </header>
  );
};
