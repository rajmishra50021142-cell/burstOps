import React from 'react';
import { ExternalLink, LayoutDashboard, Compass, Layers, BarChart3, Cloud, Server, Sparkles } from 'lucide-react';
import { OrderedLink } from '../types';

interface ResourceLinksProps {
  heading: string;
  links: OrderedLink[];
}

export const ResourceLinks: React.FC<ResourceLinksProps> = ({ heading, links }) => {
  const getIconForLink = (number: number) => {
    switch (number) {
      case 1:
        return <Layers className="w-4 h-4 text-cyan-400" />;
      case 2:
        return <LayoutDashboard className="w-4 h-4 text-amber-400" />;
      case 3:
        return <BarChart3 className="w-4 h-4 text-purple-400" />;
      case 4:
      case 5:
        return <Server className="w-4 h-4 text-emerald-400" />;
      case 6:
      case 7:
        return <Cloud className="w-4 h-4 text-sky-400" />;
      default:
        return <Compass className="w-4 h-4 text-blue-400" />;
    }
  };

  return (
    <div className="bg-slate-900/80 rounded-xl border border-slate-800 p-6 shadow-xl space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Compass className="w-5 h-5 text-cyan-400" />
            {heading}
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Direct deep-links to examine real cloud telemetry and infrastructure state on Azure.
          </p>
        </div>

        {/* Featured Grafana Quick Jump Button */}
        {links.find((l) => l.number === 2) && (
          <a
            href={links.find((l) => l.number === 2)?.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-gradient-to-r from-amber-500/20 to-orange-500/20 hover:from-amber-500/30 hover:to-orange-500/30 border border-amber-500/40 text-amber-300 font-medium text-xs shadow-md transition-all self-start sm:self-auto hover:scale-[1.02]"
          >
            <LayoutDashboard className="w-4 h-4 text-amber-400" />
            <span>Open Grafana Dashboard</span>
            <ExternalLink className="w-3.5 h-3.5 ml-1 opacity-70" />
          </a>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
        {links.map((link) => {
          const isGrafana = link.number === 2;
          return (
            <a
              key={link.number}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className={`group flex items-start gap-3 p-3.5 rounded-lg border transition-all duration-150 ${
                isGrafana
                  ? 'bg-amber-950/20 border-amber-500/30 hover:border-amber-400/60 hover:bg-amber-950/30'
                  : 'bg-slate-850/70 border-slate-750 hover:border-blue-500/40 hover:bg-slate-800'
              }`}
            >
              <div
                className={`w-7 h-7 rounded-md flex items-center justify-center shrink-0 text-xs font-bold font-mono border ${
                  isGrafana
                    ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    : 'bg-slate-800 text-slate-300 border-slate-700 group-hover:border-blue-500/40 group-hover:text-blue-300'
                }`}
              >
                {link.number}
              </div>

              <div className="flex-1 min-w-0 space-y-0.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-semibold text-xs text-white group-hover:text-cyan-300 transition-colors truncate flex items-center gap-1.5">
                    {getIconForLink(link.number)}
                    <span>{link.title}</span>
                    {isGrafana && (
                      <span className="text-[10px] font-sans font-semibold px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        Primary Telemetry
                      </span>
                    )}
                  </div>
                  <ExternalLink className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 shrink-0 transition-colors" />
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
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
