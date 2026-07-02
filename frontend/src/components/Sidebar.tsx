import React from 'react';
import type { SavedAudit, AnalysisResponse } from '../types';
import { History, ShieldAlert, ChevronRight } from 'lucide-react';
import clsx from 'clsx';

interface SidebarProps {
  audits: SavedAudit[];
  onSelectAudit: (audit: AnalysisResponse) => void;
  activeSessionId: string | null;
}

export const Sidebar: React.FC<SidebarProps> = ({ audits, onSelectAudit, activeSessionId }) => {
  return (
    <div className="w-64 bg-slate-900 border-r border-slate-800 h-screen overflow-y-auto flex flex-col">
      <div className="p-4 border-b border-slate-800">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
          <History size={16} />
          Previous Audits
        </h2>
      </div>
      <div className="flex-1 p-2 space-y-1">
        {audits.length === 0 ? (
          <div className="p-4 text-xs text-slate-500 text-center font-mono">
            No history found.
          </div>
        ) : (
          audits.map((audit) => {
            const isActive = activeSessionId === audit.session_id;
            const isHighRisk = audit.data.overall_risk_level === 'HIGH' || audit.data.overall_risk_level === 'CRITICAL';
            
            return (
              <button
                key={audit.session_id}
                onClick={() => onSelectAudit({
                  status: 'success',
                  vendor: audit.vendor,
                  session_id: audit.session_id,
                  risk_assessment: audit.data
                })}
                className={clsx(
                  "w-full text-left p-3 rounded-md transition-all duration-200 flex items-center justify-between group",
                  isActive ? "bg-slate-800 shadow-inner" : "hover:bg-slate-800/50"
                )}
              >
                <div className="flex flex-col gap-1 overflow-hidden">
                  <div className="flex items-center gap-2">
                    {isHighRisk && <ShieldAlert size={14} className="text-red-500 flex-shrink-0" />}
                    <span className="font-mono text-sm font-semibold truncate text-slate-200 group-hover:text-cyan-400 transition-colors">
                      {audit.vendor}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500 font-mono">
                    {new Date(audit.timestamp).toLocaleDateString()}
                  </span>
                </div>
                <ChevronRight size={14} className={clsx("text-slate-600 transition-transform", isActive ? "text-cyan-400 translate-x-1" : "group-hover:text-slate-400")} />
              </button>
            );
          })
        )}
      </div>
    </div>
  );
};
