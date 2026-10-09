import React from 'react';
import { Cloud, Server, ShieldCheck, Zap } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
                <Zap className="w-5 h-5 text-white" />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                BurstOps
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  Layer-7 Elastic Burst Gateway
                </span>
              </h1>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 max-w-3xl">
              Kubernetes handles baseline traffic. When demand creates a burst, the existing gateway deflects overflow to Azure Functions while Kubernetes responds through its own scaling process.
            </p>
          </div>

          <div className="flex items-center gap-2 self-start md:self-auto flex-wrap">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-slate-800/80 border border-slate-700/60 text-xs text-slate-300">
              <Cloud className="w-3.5 h-3.5 text-sky-400" />
              <span>Azure <strong className="text-white font-medium">centralindia</strong></span>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-slate-800/80 border border-slate-700/60 text-xs text-slate-300">
              <Server className="w-3.5 h-3.5 text-emerald-400" />
              <span>AKS <strong className="text-white font-medium">v1.35.8</strong></span>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-slate-800/80 border border-slate-700/60 text-xs text-slate-300">
              <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
              <span>HMAC-SHA256 Auth</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
