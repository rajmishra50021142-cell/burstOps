import React from 'react';
import { ExternalLink, LayoutDashboard, Compass, Layers, BarChart3, Cloud, Server } from 'lucide-react';
import { OrderedLink } from '../types';

interface ResourceLinksProps {
  heading: string;
  links: OrderedLink[];
}

export const ResourceLinks: React.FC<ResourceLinksProps> = ({ heading, links }) => {
  const getIconForLink = (number: number) => {
    switch (number) {
      case 1:
        return <Layers className="w-4 h-4 text-azure-500" />;
      case 2:
        return <LayoutDashboard className="w-4 h-4 text-amber-500" />;
      case 3:
        return <BarChart3 className="w-4 h-4 text-purple-500" />;
      case 4:
      case 5:
        return <Server className="w-4 h-4 text-emerald-500" />;
      case 6:
      case 7:
        return <Cloud className="w-4 h-4 text-sky-500" />;
      default:
        return <Compass className="w-4 h-4 text-azure-500" />;
    }
  };

  const grafanaItem = links.find((l) => l.number === 2);

  return (
    <div className="azure-card bg-white dark:bg-[#1B1A19] border border-[#EDEBE9] dark:border-[#292827] rounded-sm p-5 shadow-xs space-y-4 select-none">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#EDEBE9] dark:border-[#292827]">
        <div>
          <h2 className="text-sm sm:text-base font-semibold text-[#323130] dark:text-white flex items-center gap-2">
            <Compass className="w-4 h-4 text-azure-500" />
            {heading}
          </h2>
          <p className="text-xs text-[#605E5C] dark:text-[#A19F9D] mt-0.5">
            Direct deep-links to examine real cloud telemetry and infrastructure state on Azure.
          </p>
        </div>

        {/* Featured Grafana Quick Jump Button */}
        {grafanaItem && (
          <a
            href={grafanaItem.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-amber-50 dark:bg-amber-950/40 hover:bg-amber-100 dark:hover:bg-amber-950 border border-amber-300 dark:border-amber-700 text-amber-700 dark:text-amber-300 font-semibold text-xs shadow-xs transition-all self-start sm:self-auto"
          >
            <LayoutDashboard className="w-3.5 h-3.5 text-amber-600" />
            <span>Open Grafana Dashboard</span>
            <ExternalLink className="w-3 h-3 ml-0.5 opacity-70" />
          </a>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {links.map((link) => {
          const isGrafana = link.number === 2;
          return (
            <a
              key={link.number}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className={`group flex items-start gap-3 p-3.5 rounded-sm border transition-all ${
                isGrafana
                  ? 'bg-amber-50/30 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800/60 hover:border-amber-400'
                  : 'bg-[#FAF9F8] dark:bg-[#11100F] border-[#EDEBE9] dark:border-[#292827] hover:border-azure-400'
              }`}
            >
              <div
                className={`w-6 h-6 rounded-sm flex items-center justify-center shrink-0 text-xs font-bold font-mono border ${
                  isGrafana
                    ? 'bg-amber-100 dark:bg-amber-900/60 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700'
                    : 'bg-white dark:bg-black/30 text-azure-600 dark:text-azure-400 border-[#EDEBE9] dark:border-[#292827]'
                }`}
              >
                {link.number}
              </div>

              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-semibold text-xs text-[#323130] dark:text-white group-hover:text-azure-600 dark:group-hover:text-azure-400 transition-colors truncate flex items-center gap-1.5">
                    {getIconForLink(link.number)}
                    <span>{link.title}</span>
                    {isGrafana && (
                      <span className="text-[10px] font-semibold px-1.5 py-0.2 rounded bg-amber-100 dark:bg-amber-900/60 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-700">
                        Primary Telemetry
                      </span>
                    )}
                  </div>
                  <ExternalLink className="w-3.5 h-3.5 text-slate-400 group-hover:text-azure-500 shrink-0 transition-colors" />
                </div>
                <p className="text-[11px] text-[#605E5C] dark:text-[#A19F9D] leading-relaxed">
                  {link.description}
                </p>
                <div className="text-[10px] font-mono text-slate-400 truncate pt-0.5">
                  {link.url}
                </div>
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
};
