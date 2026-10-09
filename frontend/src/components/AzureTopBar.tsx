import React, { useState, useEffect, useRef } from 'react';
import {
  Menu,
  Search,
  Bell,
  Settings,
  HelpCircle,
  Terminal,
  Activity,
  Layers,
  BarChart3,
  DollarSign,
  Cpu,
  FileText,
  HeartPulse,
  X,
  ExternalLink,
  Sun,
  Moon,
  Check,
  RefreshCw,
} from 'lucide-react';
import { PortalBlade, PortalNotification } from '../types';

interface AzureTopBarProps {
  onToggleSidebar: () => void;
  activeBlade: PortalBlade;
  onNavigate: (blade: PortalBlade) => void;
  isOnline: boolean;
  routingMode: number; // 0 = baseline, 1 = burst
  cpuPercent: number;
  notifications: PortalNotification[];
  onMarkNotificationsRead: () => void;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  gatewayUrl: string;
  onSaveGatewayUrl: (url: string) => void;
}

export const AzureTopBar: React.FC<AzureTopBarProps> = ({
  onToggleSidebar,
  activeBlade,
  onNavigate,
  isOnline,
  routingMode,
  cpuPercent,
  notifications,
  onMarkNotificationsRead,
  theme,
  onToggleTheme,
  gatewayUrl,
  onSaveGatewayUrl,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [tempGatewayUrl, setTempGatewayUrl] = useState(gatewayUrl);
  const [urlSavedFeedback, setUrlSavedFeedback] = useState(false);

  const searchRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);

  const unreadCount = notifications.filter((n) => !n.read).length;

  // Search items database
  const searchResults = [
    { title: 'Gateway — Layer-7 Elastic Router', blade: 'gateway' as PortalBlade, type: 'Service', icon: Layers },
    { title: 'Monitor — Metrics & Real-time Charts', blade: 'metrics' as PortalBlade, type: 'Monitoring', icon: BarChart3 },
    { title: 'Cost Management & Billing (FinOps)', blade: 'cost' as PortalBlade, type: 'Cost Management', icon: DollarSign },
    { title: 'Load Test & Traffic Simulation', blade: 'load-test' as PortalBlade, type: 'DevOps & Testing', icon: Cpu },
    { title: 'Activity log — Event Stream', blade: 'activity-log' as PortalBlade, type: 'Governance', icon: FileText },
    { title: 'Service health — Status Matrix', blade: 'service-health' as PortalBlade, type: 'Health', icon: HeartPulse },
    { title: 'All resources', blade: 'all-resources' as PortalBlade, type: 'Catalog', icon: Activity },
  ].filter((item) =>
    searchQuery.trim() === '' ||
    item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.type.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Close search/notif popups when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setIsSearchOpen(false);
      }
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setIsNotifOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Keyboard shortcut (G+/ or /) for search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.key === '/' || (e.ctrlKey && e.key === '/')) && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault();
        setIsSearchOpen(true);
        const el = document.getElementById('azure-global-search') as HTMLInputElement;
        el?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSelectSearchResult = (blade: PortalBlade) => {
    onNavigate(blade);
    setIsSearchOpen(false);
    setSearchQuery('');
  };

  const handleSaveUrl = (e: React.FormEvent) => {
    e.preventDefault();
    onSaveGatewayUrl(tempGatewayUrl);
    setUrlSavedFeedback(true);
    setTimeout(() => setUrlSavedFeedback(false), 2000);
  };

  return (
    <header className="h-12 bg-[#001833] dark:bg-[#11100F] border-b border-[#002447] dark:border-[#292827] text-white flex items-center justify-between px-3 z-50 select-none sticky top-0">
      {/* Left: Hamburger & Portal Branding */}
      <div className="flex items-center gap-3 shrink-0">
        <button
          onClick={onToggleSidebar}
          className="w-8 h-8 flex items-center justify-center hover:bg-white/10 active:bg-white/15 rounded-sm transition-colors text-white"
          title="Expand/collapse sidebar"
          aria-label="Toggle navigation"
        >
          <Menu className="w-4 h-4" />
        </button>

        {/* BurstOps Portal Logo */}
        <button
          onClick={() => onNavigate('home')}
          className="flex items-center gap-2 group text-left focus:outline-none"
        >
          {/* Custom Geometric BurstOps Azure Mark */}
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

      {/* Center: Azure Global Search Box */}
      <div ref={searchRef} className="relative flex-1 max-w-xl mx-4 hidden sm:block">
        <div className="relative">
          <input
            id="azure-global-search"
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setIsSearchOpen(true);
            }}
            onFocus={() => setIsSearchOpen(true)}
            placeholder="Search resources, services, and docs (G+/)"
            className="w-full h-8 pl-8 pr-16 bg-[#002447] dark:bg-[#1B1A19] hover:bg-[#00305E] dark:hover:bg-[#252423] focus:bg-white focus:text-[#323130] focus:placeholder-gray-500 border border-transparent focus:border-azure-500 rounded-sm text-xs text-white placeholder-slate-400 focus:outline-none transition-colors"
          />
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5 pointer-events-none" />
          <span className="absolute right-2.5 top-2 text-[10px] font-mono text-slate-400 border border-slate-600/60 rounded px-1 pointer-events-none">
            G+/
          </span>
        </div>

        {/* Search Results Dropdown */}
        {isSearchOpen && (
          <div className="absolute top-9 left-0 right-0 bg-white dark:bg-[#1B1A19] text-[#323130] dark:text-[#F3F2F1] border border-[#EDEBE9] dark:border-[#292827] rounded-sm shadow-azureElevated z-50 overflow-hidden text-xs max-h-80 overflow-y-auto">
            <div className="px-3 py-1.5 bg-[#FAF9F8] dark:bg-[#11100F] border-b border-[#EDEBE9] dark:border-[#292827] text-[11px] font-semibold text-[#605E5C] dark:text-[#A19F9D]">
              Services & Resources
            </div>
            {searchResults.length === 0 ? (
              <div className="p-4 text-center text-slate-400">No resources found matching "{searchQuery}"</div>
            ) : (
              searchResults.map((item) => {
                const IconComponent = item.icon;
                return (
                  <button
                    key={item.blade}
                    onClick={() => handleSelectSearchResult(item.blade)}
                    className="w-full px-3 py-2 flex items-center justify-between hover:bg-[#F3F2F1] dark:hover:bg-[#252423] text-left transition-colors"
                  >
                    <div className="flex items-center gap-2.5">
                      <IconComponent className="w-4 h-4 text-azure-500 shrink-0" />
                      <div>
                        <div className="font-medium text-xs">{item.title}</div>
                        <div className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">{item.type}</div>
                      </div>
                    </div>
                    <span className="text-[11px] text-azure-500">Jump →</span>
                  </button>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* Right: Live Status Pill & Toolbar Icons */}
      {/* NOTE: Strictly NO top-right badges from Image 2! */}
      <div className="flex items-center gap-1 sm:gap-2">
        {/* Gateway Status Pill */}
        <div
          onClick={() => onNavigate('gateway')}
          className="cursor-pointer flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-black/20 hover:bg-black/35 border border-white/10 text-xs text-slate-200 transition-colors mr-1"
          title={`Observed CPU: ${cpuPercent}% | Click to view Gateway blade`}
        >
          {isOnline ? (
            routingMode === 1 ? (
              <>
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
                <span className="font-medium text-amber-300">Burst Mode (≥80%)</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                <span className="font-medium text-emerald-300">Baseline (&lt;80%)</span>
              </>
            )
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-rose-400"></span>
              <span className="font-medium text-rose-300">Gateway Standby</span>
            </>
          )}
        </div>

        {/* Cloud Shell (Terminal) Shortcut */}
        <button
          onClick={() => onNavigate('load-test')}
          className="w-8 h-8 flex items-center justify-center hover:bg-white/10 rounded-sm text-slate-300 hover:text-white transition-colors relative"
          title="Cloud Shell / Load Generator Console"
          aria-label="Cloud Shell"
        >
          <Terminal className="w-4 h-4" />
        </button>

        {/* Notifications Bell */}
        <div ref={notifRef} className="relative">
          <button
            onClick={() => {
              setIsNotifOpen(!isNotifOpen);
              if (!isNotifOpen) onMarkNotificationsRead();
            }}
            className="w-8 h-8 flex items-center justify-center hover:bg-white/10 rounded-sm text-slate-300 hover:text-white transition-colors relative"
            title="Notifications"
            aria-label="Notifications"
          >
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 bg-azure-500 rounded-full ring-2 ring-[#001833]"></span>
            )}
          </button>

          {/* Notifications Flyout Drawer */}
          {isNotifOpen && (
            <div className="absolute right-0 top-10 w-80 sm:w-96 bg-white dark:bg-[#1B1A19] text-[#323130] dark:text-[#F3F2F1] border border-[#EDEBE9] dark:border-[#292827] rounded-sm shadow-azureElevated z-50 overflow-hidden text-xs">
              <div className="px-4 py-2.5 bg-[#FAF9F8] dark:bg-[#11100F] border-b border-[#EDEBE9] dark:border-[#292827] flex items-center justify-between">
                <span className="font-semibold text-xs text-[#323130] dark:text-white">Notifications</span>
                <button
                  onClick={() => setIsNotifOpen(false)}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-white"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="max-h-80 overflow-y-auto divide-y divide-[#EDEBE9] dark:divide-[#292827]">
                {notifications.length === 0 ? (
                  <div className="p-4 text-center text-slate-400">No recent notifications</div>
                ) : (
                  notifications.map((n) => (
                    <div key={n.id} className="p-3 hover:bg-[#F3F2F1] dark:hover:bg-[#252423] transition-colors space-y-1">
                      <div className="flex items-center justify-between">
                        <span className={`font-semibold text-[11px] ${
                          n.type === 'warning' ? 'text-amber-500' :
                          n.type === 'success' ? 'text-emerald-500' :
                          n.type === 'error' ? 'text-rose-500' : 'text-azure-500'
                        }`}>
                          {n.title}
                        </span>
                        <span className="text-[10px] text-slate-400">
                          {new Date(n.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] leading-relaxed">
                        {n.message}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Portal Settings */}
        <button
          onClick={() => setIsSettingsOpen(true)}
          className="w-8 h-8 flex items-center justify-center hover:bg-white/10 rounded-sm text-slate-300 hover:text-white transition-colors"
          title="Portal settings"
          aria-label="Settings"
        >
          <Settings className="w-4 h-4" />
        </button>

        {/* Help & Support */}
        <button
          onClick={() => setIsHelpOpen(true)}
          className="w-8 h-8 flex items-center justify-center hover:bg-white/10 rounded-sm text-slate-300 hover:text-white transition-colors"
          title="Help & docs"
          aria-label="Help"
        >
          <HelpCircle className="w-4 h-4" />
        </button>

        {/* User Avatar Circle */}
        <div
          className="w-7 h-7 rounded-full bg-azure-500 text-white font-semibold text-xs flex items-center justify-center ml-1 ring-1 ring-white/20 select-none cursor-pointer"
          title="Azure Administrator: Raj Mishra (rajmishra50021142-cell)"
        >
          RM
        </div>
      </div>

      {/* Settings Modal */}
      {isSettingsOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-[#1B1A19] text-[#323130] dark:text-[#F3F2F1] rounded-sm border border-[#EDEBE9] dark:border-[#292827] shadow-azureElevated w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-100">
            <div className="px-5 py-3.5 bg-[#FAF9F8] dark:bg-[#11100F] border-b border-[#EDEBE9] dark:border-[#292827] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Settings className="w-4 h-4 text-azure-500" />
                <h3 className="font-semibold text-sm">Portal Settings</h3>
              </div>
              <button
                onClick={() => setIsSettingsOpen(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 space-y-5 text-xs">
              {/* Theme Toggle */}
              <div className="space-y-2">
                <label className="font-semibold block text-[#323130] dark:text-white">
                  Appearance & Theme
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => { if (theme !== 'light') onToggleTheme(); }}
                    className={`p-3 rounded-sm border flex items-center gap-2.5 justify-center transition-all ${
                      theme === 'light'
                        ? 'border-azure-500 bg-azure-50 text-azure-700 font-semibold ring-1 ring-azure-500'
                        : 'border-[#EDEBE9] dark:border-[#292827] hover:bg-slate-50 dark:hover:bg-[#252423]'
                    }`}
                  >
                    <Sun className="w-4 h-4 text-amber-500" />
                    <span>Azure Light</span>
                  </button>

                  <button
                    onClick={() => { if (theme !== 'dark') onToggleTheme(); }}
                    className={`p-3 rounded-sm border flex items-center gap-2.5 justify-center transition-all ${
                      theme === 'dark'
                        ? 'border-azure-500 bg-[#002447] text-white font-semibold ring-1 ring-azure-500'
                        : 'border-[#EDEBE9] dark:border-[#292827] hover:bg-slate-50 dark:hover:bg-[#252423]'
                    }`}
                  >
                    <Moon className="w-4 h-4 text-sky-400" />
                    <span>Azure Dark</span>
                  </button>
                </div>
              </div>

              {/* Gateway URL Override */}
              <form onSubmit={handleSaveUrl} className="space-y-2 pt-2 border-t border-[#EDEBE9] dark:border-[#292827]">
                <label className="font-semibold block text-[#323130] dark:text-white">
                  Gateway API Endpoint
                </label>
                <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
                  Default: <code className="bg-slate-100 dark:bg-black/40 px-1 py-0.5 rounded">/gateway</code> (proxied to Azure Ingress)
                </p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={tempGatewayUrl}
                    onChange={(e) => setTempGatewayUrl(e.target.value)}
                    placeholder="/gateway or http://..."
                    className="flex-1 px-3 py-1.5 bg-white dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827] rounded-sm text-xs focus:outline-none focus:border-azure-500 font-mono"
                  />
                  <button type="submit" className="azure-btn-primary shrink-0">
                    {urlSavedFeedback ? (
                      <>
                        <Check className="w-3.5 h-3.5" />
                        Saved
                      </>
                    ) : (
                      'Save'
                    )}
                  </button>
                </div>
              </form>

              {/* Polling Interval Info */}
              <div className="pt-2 border-t border-[#EDEBE9] dark:border-[#292827] space-y-1 text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
                <div>• Metric Polling Interval: <strong>2.0 seconds</strong></div>
                <div>• Prometheus Scraper: <strong>gateway_cpu_observed_percent, gateway_deflect_ratio</strong></div>
                <div>• Backplane: <strong>Redis distributed master lock</strong></div>
              </div>
            </div>

            <div className="px-5 py-3 bg-[#FAF9F8] dark:bg-[#11100F] border-t border-[#EDEBE9] dark:border-[#292827] flex justify-end">
              <button onClick={() => setIsSettingsOpen(false)} className="azure-btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Help Modal */}
      {isHelpOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-[#1B1A19] text-[#323130] dark:text-[#F3F2F1] rounded-sm border border-[#EDEBE9] dark:border-[#292827] shadow-azureElevated w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-100">
            <div className="px-5 py-3.5 bg-[#FAF9F8] dark:bg-[#11100F] border-b border-[#EDEBE9] dark:border-[#292827] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-azure-500" />
                <h3 className="font-semibold text-sm">BurstOps Portal Documentation & Shortcuts</h3>
              </div>
              <button
                onClick={() => setIsHelpOpen(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 text-xs">
              <div className="space-y-1.5">
                <h4 className="font-semibold text-[#323130] dark:text-white">What is BurstOps?</h4>
                <p className="text-[#605E5C] dark:text-[#A19F9D] leading-relaxed text-[11px]">
                  BurstOps is a Layer-7 elastic burst routing gateway deployed on Microsoft Azure. Kubernetes absorbs steady-state baseline traffic. When load drives backend CPU past 80%, the gateway smoothly deflects surplus requests to Azure Functions while Kubernetes scales out via HPA. Once CPU cools below 60%, routing self-heals back to Kubernetes.
                </p>
              </div>

              <div className="space-y-2 pt-2 border-t border-[#EDEBE9] dark:border-[#292827]">
                <h4 className="font-semibold text-[#323130] dark:text-white">Keyboard Shortcuts</h4>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="flex items-center justify-between p-2 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm">
                    <span>Global Search</span>
                    <kbd className="font-mono bg-white dark:bg-black/30 px-1.5 py-0.5 rounded border border-[#EDEBE9] dark:border-[#292827]">G + /</kbd>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm">
                    <span>Toggle Sidebar</span>
                    <kbd className="font-mono bg-white dark:bg-black/30 px-1.5 py-0.5 rounded border border-[#EDEBE9] dark:border-[#292827]">Alt + S</kbd>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm">
                    <span>Go to Home</span>
                    <kbd className="font-mono bg-white dark:bg-black/30 px-1.5 py-0.5 rounded border border-[#EDEBE9] dark:border-[#292827]">G + H</kbd>
                  </div>
                  <div className="flex items-center justify-between p-2 bg-[#FAF9F8] dark:bg-[#11100F] rounded-sm">
                    <span>Open Metrics</span>
                    <kbd className="font-mono bg-white dark:bg-black/30 px-1.5 py-0.5 rounded border border-[#EDEBE9] dark:border-[#292827]">G + M</kbd>
                  </div>
                </div>
              </div>
            </div>

            <div className="px-5 py-3 bg-[#FAF9F8] dark:bg-[#11100F] border-t border-[#EDEBE9] dark:border-[#292827] flex justify-end">
              <button onClick={() => setIsHelpOpen(false)} className="azure-btn-secondary">
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
