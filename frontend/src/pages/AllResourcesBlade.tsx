import React, { useState } from 'react';
import {
  Layers,
  Search,
  Filter,
  ExternalLink,
  Cpu,
  Server,
  Zap,
  Database,
  BarChart3,
  LayoutDashboard,
} from 'lucide-react';
import { PortalBlade } from '../types';

interface AllResourcesBladeProps {
  onNavigate: (blade: PortalBlade) => void;
  isOnline: boolean;
}

export const AllResourcesBlade: React.FC<AllResourcesBladeProps> = ({ onNavigate, isOnline }) => {
  const [filterQuery, setFilterQuery] = useState('');

  const resources = [
    {
      name: 'burstops-gateway',
      type: 'Layer-7 Router (Gateway)',
      resourceGroup: 'rg-burstops-centralindia',
      location: 'Central India',
      subscription: 'Azure Student / Enterprise',
      blade: 'gateway' as PortalBlade,
      icon: Cpu,
    },
    {
      name: 'func-burstops-cvkzqc',
      type: 'Function App (Flex Consumption)',
      resourceGroup: 'rg-burstops-centralindia',
      location: 'Central India',
      subscription: 'Azure Student / Enterprise',
      blade: 'gateway' as PortalBlade,
      icon: Zap,
    },
    {
      name: 'dummy-backend-sieve',
      type: 'Kubernetes Pods (AKS)',
      resourceGroup: 'rg-burstops-centralindia',
      location: 'Central India',
      subscription: 'Azure Student / Enterprise',
      blade: 'gateway' as PortalBlade,
      icon: Server,
    },
    {
      name: 'burstops-redis-cache',
      type: 'Redis State Backplane',
      resourceGroup: 'rg-burstops-centralindia',
      location: 'Central India',
      subscription: 'Azure Student / Enterprise',
      blade: 'service-health' as PortalBlade,
      icon: Database,
    },
    {
      name: 'prometheus-k8s',
      type: 'Monitoring Workspace (PromQL)',
      resourceGroup: 'rg-burstops-centralindia',
      location: 'Central India',
      subscription: 'Azure Student / Enterprise',
      blade: 'metrics' as PortalBlade,
      icon: BarChart3,
    },
    {
      name: 'grafana-telemetry',
      type: 'Dashboard Workspace',
      resourceGroup: 'rg-burstops-centralindia',
      location: 'Central India',
      subscription: 'Azure Student / Enterprise',
      isExternal: true,
      url: 'http://localhost:3000',
      icon: LayoutDashboard,
    },
  ];

  const filtered = resources.filter(
    (r) =>
      r.name.toLowerCase().includes(filterQuery.toLowerCase()) ||
      r.type.toLowerCase().includes(filterQuery.toLowerCase())
  );

  return (
    <div className="p-4 sm:p-6 space-y-5 max-w-7xl mx-auto select-none">
      {/* Search Toolbar */}
      <div className="azure-card p-3 rounded-sm flex items-center justify-between gap-3 text-xs">
        <div className="relative flex-1 max-w-sm">
          <input
            type="text"
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            placeholder="Filter by name..."
            className="w-full px-2.5 py-1.5 pl-8 bg-white dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827] rounded-sm text-xs focus:outline-none focus:border-azure-500"
          />
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5 pointer-events-none" />
        </div>

        <div className="text-xs text-[#605E5C] dark:text-[#A19F9D]">
          Showing <strong>{filtered.length}</strong> of {resources.length} resources
        </div>
      </div>

      {/* Catalog Table */}
      <div className="azure-card rounded-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full azure-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Status</th>
                <th>Resource group</th>
                <th>Location</th>
                <th>Subscription</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => {
                const Icon = item.icon;
                return (
                  <tr key={item.name} className="transition-colors">
                    <td className="font-semibold text-azure-600 dark:text-azure-400">
                      {item.isExternal ? (
                        <a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:underline flex items-center gap-1.5">
                          <Icon className="w-3.5 h-3.5 text-azure-500" />
                          <span>{item.name}</span>
                          <ExternalLink className="w-3 h-3 text-slate-400" />
                        </a>
                      ) : (
                        <button onClick={() => item.blade && onNavigate(item.blade)} className="hover:underline flex items-center gap-1.5 text-left">
                          <Icon className="w-3.5 h-3.5 text-azure-500" />
                          <span>{item.name}</span>
                        </button>
                      )}
                    </td>
                    <td className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] font-mono">{item.type}</td>
                    <td>
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        Active
                      </span>
                    </td>
                    <td className="text-azure-600 dark:text-azure-400 hover:underline cursor-pointer">{item.resourceGroup}</td>
                    <td className="text-[#605E5C] dark:text-[#A19F9D]">{item.location}</td>
                    <td className="text-[#605E5C] dark:text-[#A19F9D]">{item.subscription}</td>
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
