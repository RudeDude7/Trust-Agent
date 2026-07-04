import React, { useState, useEffect, useCallback } from 'react';
import type { GapAction, SavedAudit } from '../types';
import { updateGapStatus, fetchGapActions } from '../api';
import { CheckCircle2, AlertTriangle, Shield, FileText, ChevronDown, ChevronUp, MessageSquare } from 'lucide-react';
import clsx from 'clsx';

interface GapMatrixProps {
  data: SavedAudit;
}

type GapStatus = 'open' | 'accepted' | 'remediation' | 'exemption';
type GapCategory = 'osint' | 'rag' | 'data_gap';

interface GapRow {
  text: string;
  category: GapCategory;
  index: number;
  status: GapStatus;
  note: string;
}

const STATUS_CONFIG: Record<GapStatus, { label: string; color: string; bg: string; border: string }> = {
  open: { label: 'OPEN', color: 'text-slate-400', bg: 'bg-slate-700/50', border: 'border-slate-600' },
  accepted: { label: 'ACCEPTED', color: 'text-emerald-400', bg: 'bg-emerald-900/30', border: 'border-emerald-500/50' },
  remediation: { label: 'REMEDIATION', color: 'text-amber-400', bg: 'bg-amber-900/30', border: 'border-amber-500/50' },
  exemption: { label: 'EXEMPTION', color: 'text-blue-400', bg: 'bg-blue-900/30', border: 'border-blue-500/50' },
};

const CATEGORY_CONFIG: Record<GapCategory, { label: string; icon: React.ReactNode; color: string }> = {
  osint: { label: 'OSINT', icon: <Shield size={14} />, color: 'text-amber-500' },
  rag: { label: 'RAG', icon: <FileText size={14} />, color: 'text-indigo-400' },
  data_gap: { label: 'GAP', icon: <AlertTriangle size={14} />, color: 'text-slate-500' },
};

export const GapMatrix: React.FC<GapMatrixProps> = ({ data }) => {
  const { risk_assessment, session_id } = data;
  const [gaps, setGaps] = useState<GapRow[]>([]);
  const [expandedIdx, setExpandedIdx] = useState<string | null>(null);
  const [noteInputs, setNoteInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  // Build the unified gap list from all three inference arrays
  const buildGaps = useCallback((actions: GapAction[]) => {
    const actionMap = new Map<string, GapAction>();
    actions.forEach(a => actionMap.set(`${a.category}-${a.gap_index}`, a));

    const rows: GapRow[] = [];

    risk_assessment.osint_inferences.forEach((text, idx) => {
      const key = `osint-${idx}`;
      const action = actionMap.get(key);
      rows.push({ text, category: 'osint', index: idx, status: action?.status || 'open', note: action?.note || '' });
    });

    risk_assessment.rag_inferences.forEach((text, idx) => {
      const key = `rag-${idx}`;
      const action = actionMap.get(key);
      rows.push({ text, category: 'rag', index: idx, status: action?.status || 'open', note: action?.note || '' });
    });

    risk_assessment.data_gaps.forEach((text, idx) => {
      const key = `data_gap-${idx}`;
      const action = actionMap.get(key);
      rows.push({ text, category: 'data_gap', index: idx, status: action?.status || 'open', note: action?.note || '' });
    });

    return rows;
  }, [risk_assessment]);

  useEffect(() => {
    fetchGapActions(session_id)
      .then(actions => setGaps(buildGaps(actions)))
      .catch(() => setGaps(buildGaps([])));
  }, [session_id, buildGaps]);

  const handleStatusChange = async (gap: GapRow, newStatus: GapStatus) => {
    const key = `${gap.category}-${gap.index}`;
    setSaving(key);
    try {
      const note = noteInputs[key] ?? gap.note;
      const updatedActions = await updateGapStatus(session_id, gap.index, gap.category, newStatus, note);
      setGaps(buildGaps(updatedActions));
    } catch (err) {
      console.error('Failed to update gap status:', err);
    } finally {
      setSaving(null);
    }
  };

  const handleSaveNote = async (gap: GapRow) => {
    const key = `${gap.category}-${gap.index}`;
    setSaving(key);
    try {
      const note = noteInputs[key] ?? gap.note;
      const updatedActions = await updateGapStatus(session_id, gap.index, gap.category, gap.status, note);
      setGaps(buildGaps(updatedActions));
    } catch (err) {
      console.error('Failed to save note:', err);
    } finally {
      setSaving(null);
    }
  };

  // Progress calculation
  const totalGaps = gaps.length;
  const resolvedGaps = gaps.filter(g => g.status !== 'open').length;
  const progressPct = totalGaps > 0 ? Math.round((resolvedGaps / totalGaps) * 100) : 0;

  if (totalGaps === 0) {
    return (
      <div className="text-center py-12 text-slate-500 font-mono text-sm">
        <CheckCircle2 size={40} className="mx-auto mb-4 text-emerald-500" />
        No compliance gaps identified. This vendor passed all checks.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Progress Bar */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-mono text-slate-400">
            RESOLUTION PROGRESS
          </span>
          <span className="text-sm font-mono font-bold text-cyan-400">
            {resolvedGaps} / {totalGaps} resolved ({progressPct}%)
          </span>
        </div>
        <div className="h-2.5 bg-slate-700 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500 ease-out"
            style={{
              width: `${progressPct}%`,
              background: progressPct === 100
                ? 'linear-gradient(90deg, #10b981, #34d399)'
                : 'linear-gradient(90deg, #06b6d4, #8b5cf6)',
            }}
          />
        </div>
        <div className="flex gap-4 mt-3 text-xs font-mono">
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> Accepted: {gaps.filter(g => g.status === 'accepted').length}</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-500 inline-block" /> Remediation: {gaps.filter(g => g.status === 'remediation').length}</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-500 inline-block" /> Exemption: {gaps.filter(g => g.status === 'exemption').length}</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-slate-500 inline-block" /> Open: {gaps.filter(g => g.status === 'open').length}</span>
        </div>
      </div>

      {/* Gap Rows */}
      <div className="space-y-2">
        {gaps.map((gap) => {
          const key = `${gap.category}-${gap.index}`;
          const statusCfg = STATUS_CONFIG[gap.status];
          const catCfg = CATEGORY_CONFIG[gap.category];
          const isExpanded = expandedIdx === key;
          const isSaving = saving === key;

          return (
            <div
              key={key}
              className={clsx(
                'rounded-lg border transition-all duration-200',
                statusCfg.border,
                statusCfg.bg
              )}
            >
              {/* Main Row */}
              <div className="flex items-center gap-3 p-4">
                {/* Category Badge */}
                <span className={clsx('flex items-center gap-1 text-[10px] font-mono font-bold uppercase tracking-widest w-16 shrink-0', catCfg.color)}>
                  {catCfg.icon} {catCfg.label}
                </span>

                {/* Gap Text */}
                <p className="flex-1 text-sm text-slate-300 leading-relaxed">{gap.text}</p>

                {/* Status Selector */}
                <select
                  value={gap.status}
                  onChange={(e) => handleStatusChange(gap, e.target.value as GapStatus)}
                  disabled={isSaving}
                  className={clsx(
                    'text-xs font-mono font-bold uppercase px-3 py-1.5 rounded-md border cursor-pointer transition-colors',
                    'bg-slate-900 focus:outline-none focus:ring-1 focus:ring-cyan-500',
                    statusCfg.color, statusCfg.border,
                    isSaving && 'opacity-50 cursor-wait'
                  )}
                >
                  <option value="open">⊘ Open</option>
                  <option value="accepted">✓ Accept Risk</option>
                  <option value="remediation">⚠ Remediate</option>
                  <option value="exemption">↗ Exempt</option>
                </select>

                {/* Expand Note Button */}
                <button
                  onClick={() => setExpandedIdx(isExpanded ? null : key)}
                  className="text-slate-500 hover:text-slate-300 transition-colors p-1"
                  title="Add internal note"
                >
                  <MessageSquare size={16} />
                  {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
              </div>

              {/* Collapsible Note Area */}
              {isExpanded && (
                <div className="px-4 pb-4 pt-0 border-t border-slate-700/30">
                  <label className="text-[10px] font-mono text-slate-500 uppercase tracking-widest block mb-2 mt-3">
                    Internal Team Note
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={noteInputs[key] ?? gap.note}
                      onChange={(e) => setNoteInputs(prev => ({ ...prev, [key]: e.target.value }))}
                      placeholder="e.g., Assigned to John — awaiting vendor response by Q3..."
                      className="flex-1 bg-slate-900 border border-slate-600 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
                    />
                    <button
                      onClick={() => handleSaveNote(gap)}
                      disabled={isSaving}
                      className="bg-cyan-700 hover:bg-cyan-600 text-white text-xs font-mono px-4 py-2 rounded transition-colors disabled:opacity-50"
                    >
                      {isSaving ? '...' : 'SAVE'}
                    </button>
                  </div>
                  {gap.note && noteInputs[key] === undefined && (
                    <p className="text-xs text-slate-500 mt-2 font-mono italic">
                      Current note: "{gap.note}"
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
