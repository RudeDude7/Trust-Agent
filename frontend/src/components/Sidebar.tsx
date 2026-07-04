import React from 'react';
import type { SavedAudit } from '../types';
import { History, ShieldAlert, ChevronRight, Bell } from 'lucide-react';
import clsx from 'clsx';

interface SidebarProps {
  audits: SavedAudit[];
  onSelectAudit: (audit: SavedAudit) => void;
  onOpenThreatFeed: () => void;
  activeSessionId: string | null;
  isThreatFeedOpen: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ audits, onSelectAudit, onOpenThreatFeed, activeSessionId, isThreatFeedOpen }) => {
  return (
    <div className="w-64 bg-slate-900 border-r border-slate-800 h-screen overflow-y-auto flex flex-col">
      <div className="p-4 border-b border-slate-800">
        <button
          onClick={onOpenThreatFeed}
          className={clsx(
            "w-full flex items-center justify-between p-3 rounded-lg font-mono font-bold transition-all",
            isThreatFeedOpen ? "bg-fuchsia-900/30 text-fuchsia-400 border border-fuchsia-500/50" : "bg-slate-800 text-slate-300 hover:bg-slate-700"
          )}
        >
          <span className="flex items-center gap-2">
            <Bell size={18} className={isThreatFeedOpen ? "text-fuchsia-500" : "text-slate-400"} />
            Live Threats
          </span>
          <ChevronRight size={16} />
        </button>
      </div>
      
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
            const isHighRisk = audit.risk_assessment.overall_risk_level === 'HIGH' || audit.risk_assessment.overall_risk_level === 'CRITICAL';
            
            return (
              <button
                key={audit.session_id}
                onClick={() => onSelectAudit(audit)}
                className={clsx(
                  "w-full text-left p-3 rounded-md transition-all duration-200 flex items-center justify-between group",
                  isActive ? "bg-slate-800 shadow-inner" : "hover:bg-slate-800/50"
                )}
              >
                <div className="flex flex-col gap-1 overflow-hidden">
                  <div className="flex items-center gap-2">
                    {isHighRisk && <ShieldAlert size={14} className="text-red-500 flex-shrink-0" />}
                    <span className="font-mono text-sm font-semibold truncate text-slate-200 group-hover:text-cyan-400 transition-colors">
                      {audit.vendor_name}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500 font-mono">
                    {new Date(audit.created_at).toLocaleDateString()}
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
