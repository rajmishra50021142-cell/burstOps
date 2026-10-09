import React, { useState } from 'react';
import {
  FileText,
  Filter,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Flame,
  RotateCcw,
  RefreshCw,
  Search,
} from 'lucide-react';
import { ActivityLogItem } from '../types';

interface ActivityLogBladeProps {
  logs: ActivityLogItem[];
  onRefresh: () => void;
}

export const ActivityLogBlade: React.FC<ActivityLogBladeProps> = ({ logs, onRefresh }) => {
  const [filterType, setFilterType] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const filterChips = ['All', 'Burst Deflection', 'Baseline Recovery', 'Gateway Initialization'];

  const filteredLogs = logs.filter((item) => {
    const matchesFilter =
      filterType === 'All' ||
      item.operationName.toLowerCase().includes(filterType.toLowerCase());

    const matchesSearch =
      searchQuery.trim() === '' ||
      item.operationName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.details.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.resource.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesFilter && matchesSearch;
  });

  return (
    <div className="p-4 sm:p-6 space-y-5 max-w-7xl mx-auto select-none">
      {/* Header and Filter Toolbar */}
      <div className="azure-card p-4 rounded-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#EDEBE9] dark:border-[#292827]">
          <div>
            <h2 className="font-semibold text-xs text-[#323130] dark:text-white flex items-center gap-2">
              <FileText className="w-4 h-4 text-azure-500" />
              Activity Log Events
            </h2>
            <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D]">
              Client-side audit trail recording routing mode state transitions and controller events.
            </p>
          </div>

          <button onClick={onRefresh} className="azure-btn-secondary text-xs self-start sm:self-auto">
            <RefreshCw className="w-3.5 h-3.5 text-azure-500" />
            <span>Refresh</span>
          </button>
        </div>

        {/* Filter Chips & Search Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[#605E5C] dark:text-[#A19F9D] mr-1">Filter:</span>
            {filterChips.map((chip) => (
              <button
                key={chip}
                onClick={() => setFilterType(chip)}
                className={`px-2.5 py-1 rounded-sm border transition-colors ${
                  filterType === chip
                    ? 'bg-azure-500 border-azure-500 text-white font-semibold'
                    : 'bg-[#FAF9F8] dark:bg-[#11100F] border-[#EDEBE9] dark:border-[#292827] text-[#323130] dark:text-[#F3F2F1] hover:bg-[#F3F2F1]'
                }`}
              >
                {chip}
              </button>
            ))}
          </div>

          <div className="relative min-w-48">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search activity events..."
              className="w-full px-2.5 py-1 pl-7 bg-white dark:bg-[#11100F] border border-[#EDEBE9] dark:border-[#292827] rounded-sm text-xs focus:outline-none focus:border-azure-500"
            />
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2 top-2 pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Activity Log Table */}
      <div className="azure-card rounded-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full azure-table">
            <thead>
              <tr>
                <th>Event Time</th>
                <th>Operation Name</th>
                <th>Status</th>
                <th>Initiated By</th>
                <th>Resource</th>
                <th>CPU %</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-slate-400">
                    No activity log events match the current filter.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr key={log.id} className="transition-colors">
                    <td className="font-mono text-[11px] text-[#605E5C] dark:text-[#A19F9D] whitespace-nowrap">
                      {log.timestamp}
                    </td>
                    <td className="font-semibold text-azure-600 dark:text-azure-400">
                      <div className="flex items-center gap-1.5">
                        {log.operationName.includes('Burst') ? (
                          <Flame className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                        ) : log.operationName.includes('Recovery') ? (
                          <RotateCcw className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                        ) : (
                          <FileText className="w-3.5 h-3.5 text-azure-500 shrink-0" />
                        )}
                        <span>{log.operationName}</span>
                      </div>
                    </td>
                    <td>
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300">
                        <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                        {log.status}
                      </span>
                    </td>
                    <td className="font-mono text-[11px]">{log.initiatedBy}</td>
                    <td className="font-mono text-[11px] text-[#605E5C] dark:text-[#A19F9D]">{log.resource}</td>
                    <td className="font-mono text-[11px] font-semibold text-azure-600 dark:text-azure-400">
                      {log.cpuPercent !== undefined ? `${log.cpuPercent}%` : '-'}
                    </td>
                    <td className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] max-w-xs truncate" title={log.details}>
                      {log.details}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
