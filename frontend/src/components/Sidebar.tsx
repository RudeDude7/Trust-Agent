import React from 'react';
import type { SavedAudit } from '../types';
import { History, ShieldAlert, ChevronRight, Bell, Users, Trash2 } from 'lucide-react';
import clsx from 'clsx';

interface SidebarProps {
  audits: SavedAudit[];
  onSelectAudit: (audit: SavedAudit) => void;
  onOpenThreatFeed: () => void;
  onOpenTeamSettings: () => void;
  onDeleteAudit: (sessionId: string) => void;
  activeSessionId: string | null;
  isThreatFeedOpen: boolean;
  isTeamSettingsOpen: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ audits, onSelectAudit, onOpenThreatFeed, onOpenTeamSettings, onDeleteAudit, activeSessionId, isThreatFeedOpen, isTeamSettingsOpen }) => {
  return (
    <div className="w-64 bg-white border-r border-stone-200 h-screen overflow-y-auto flex flex-col shadow-[1px_0_10px_rgba(0,0,0,0.01)]">
      <div className="p-5 border-b border-stone-100 space-y-3">
        <button
          onClick={onOpenThreatFeed}
          className={clsx(
            "w-full flex items-center justify-between p-3.5 rounded-xl font-heading font-semibold transition-all",
            isThreatFeedOpen ? "bg-accent-50 text-accent-700 border border-accent-200 shadow-sm" : "bg-white text-stone-600 hover:bg-stone-50 border border-transparent hover:border-stone-200"
          )}
        >
          <span className="flex items-center gap-2">
            <Bell size={18} className={isThreatFeedOpen ? "text-accent-600" : "text-stone-400"} />
            Live Threats
          </span>
          <ChevronRight size={16} />
        </button>

        <button
          onClick={onOpenTeamSettings}
          className={clsx(
            "w-full flex items-center justify-between p-3.5 rounded-xl font-heading font-semibold transition-all",
            isTeamSettingsOpen ? "bg-accent-50 text-accent-700 border border-accent-200 shadow-sm" : "bg-white text-stone-600 hover:bg-stone-50 border border-transparent hover:border-stone-200"
          )}
        >
          <span className="flex items-center gap-2">
            <Users size={18} className={isTeamSettingsOpen ? "text-accent-600" : "text-stone-400"} />
            Team Settings
          </span>
          <ChevronRight size={16} />
        </button>
      </div>
      
      <div className="p-5 pb-3">
        <h2 className="text-xs font-bold text-stone-400 uppercase tracking-widest flex items-center gap-2">
          <History size={14} />
          Previous Audits
        </h2>
      </div>
      <div className="flex-1 p-3 pt-0 space-y-1">
        {audits.length === 0 ? (
          <div className="p-4 text-sm text-stone-400 text-center italic">
            No history found.
          </div>
        ) : (
          audits.map((audit) => {
            const isActive = activeSessionId === audit.session_id && !isThreatFeedOpen && !isTeamSettingsOpen;
            const isHighRisk = audit.risk_assessment.overall_risk_level === 'HIGH' || audit.risk_assessment.overall_risk_level === 'CRITICAL';
            
            return (
              <div
                key={audit.session_id}
                className={clsx(
                  "w-full text-left p-3 rounded-xl transition-all duration-200 flex items-center justify-between group cursor-pointer border",
                  isActive ? "bg-stone-50 border-stone-200 shadow-sm" : "bg-white border-transparent hover:bg-stone-50 hover:border-stone-100"
                )}
                onClick={() => onSelectAudit(audit)}
              >
                <div className="flex flex-col gap-1 overflow-hidden flex-1">
                  <div className="flex items-center gap-2">
                    {isHighRisk && <ShieldAlert size={14} className="text-red-500 flex-shrink-0" />}
                    <span className={clsx("font-semibold text-sm truncate transition-colors", isActive ? "text-accent-700" : "text-stone-700 group-hover:text-accent-600")}>
                      {audit.vendor_name}
                    </span>
                  </div>
                  <span className="text-xs text-stone-400">
                    {new Date(audit.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteAudit(audit.session_id);
                    }}
                    className="p-1.5 text-stone-400 hover:text-red-500 rounded-lg hover:bg-white border border-transparent hover:border-stone-200 shadow-sm transition-all"
                    title="Delete Audit"
                  >
                    <Trash2 size={14} />
                  </button>
                  <ChevronRight size={14} className={clsx("transition-transform", isActive ? "text-accent-500 translate-x-1" : "text-stone-300 group-hover:text-stone-400")} />
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
