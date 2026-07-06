import React, { useState, useEffect, useCallback } from 'react';
import type { GapAction, SavedAudit } from '../types';
import { updateGapStatus, fetchGapActions, fetchEmployees } from '../api';
import { CheckCircle2, AlertTriangle, Shield, FileText, ChevronDown, ChevronUp, MessageSquare, User } from 'lucide-react';
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
  assigned_to?: string | null;
}

const STATUS_CONFIG: Record<GapStatus, { label: string; color: string; bg: string; border: string }> = {
  open: { label: 'OPEN', color: 'text-stone-500', bg: 'bg-stone-50', border: 'border-stone-200' },
  accepted: { label: 'ACCEPTED', color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200' },
  remediation: { label: 'REMEDIATION', color: 'text-orange-600', bg: 'bg-orange-50', border: 'border-orange-200' },
  exemption: { label: 'EXEMPTION', color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200' },
};

const CATEGORY_CONFIG: Record<GapCategory, { label: string; icon: React.ReactNode; color: string }> = {
  osint: { label: 'OSINT', icon: <Shield size={14} />, color: 'text-orange-500' },
  rag: { label: 'RAG', icon: <FileText size={14} />, color: 'text-accent-600' },
  data_gap: { label: 'GAP', icon: <AlertTriangle size={14} />, color: 'text-stone-500' },
};

export const GapMatrix: React.FC<GapMatrixProps> = ({ data }) => {
  const { risk_assessment, session_id } = data;
  const [gaps, setGaps] = useState<GapRow[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);
  const [expandedIdx, setExpandedIdx] = useState<string | null>(null);
  const [noteInputs, setNoteInputs] = useState<Record<string, string>>({});
  const [assignedInputs, setAssignedInputs] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  // Build the unified gap list from all three inference arrays
  const buildGaps = useCallback((actions: GapAction[]) => {
    const actionMap = new Map<string, GapAction>();
    actions.forEach(a => actionMap.set(`${a.category}-${a.gap_index}`, a));

    const rows: GapRow[] = [];

    risk_assessment.osint_inferences.forEach((text, idx) => {
      const key = `osint-${idx}`;
      const action = actionMap.get(key);
      rows.push({ text, category: 'osint', index: idx, status: action?.status || 'open', note: action?.note || '', assigned_to: action?.assigned_to });
    });

    risk_assessment.rag_inferences.forEach((text, idx) => {
      const key = `rag-${idx}`;
      const action = actionMap.get(key);
      rows.push({ text, category: 'rag', index: idx, status: action?.status || 'open', note: action?.note || '', assigned_to: action?.assigned_to });
    });

    risk_assessment.data_gaps.forEach((text, idx) => {
      const key = `data_gap-${idx}`;
      const action = actionMap.get(key);
      rows.push({ text, category: 'data_gap', index: idx, status: action?.status || 'open', note: action?.note || '', assigned_to: action?.assigned_to });
    });

    return rows;
  }, [risk_assessment]);

  useEffect(() => {
    fetchGapActions(session_id)
      .then(actions => setGaps(buildGaps(actions)))
      .catch(() => setGaps(buildGaps([])));
      
    fetchEmployees()
      .then(emps => setEmployees(emps))
      .catch(console.error);
  }, [session_id, buildGaps]);

  const handleStatusChange = async (gap: GapRow, newStatus: GapStatus) => {
    const key = `${gap.category}-${gap.index}`;
    setSaving(key);
    try {
      const note = noteInputs[key] ?? gap.note;
      const assigned = assignedInputs[key] !== undefined ? assignedInputs[key] : (gap.assigned_to || null);
      const updatedActions = await updateGapStatus(session_id, gap.index, gap.category, newStatus, note, assigned);
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
      const assigned = assignedInputs[key] !== undefined ? assignedInputs[key] : (gap.assigned_to || null);
      const updatedActions = await updateGapStatus(session_id, gap.index, gap.category, gap.status, note, assigned);
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
      <div className="text-center py-12 text-stone-500 font-semibold text-sm">
        <CheckCircle2 size={40} className="mx-auto mb-4 text-emerald-500" />
        No compliance gaps identified. This vendor passed all checks.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Progress Bar */}
      <div className="bg-stone-50 border border-stone-200 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-stone-500 uppercase tracking-widest">
            Resolution Progress
          </span>
          <span className="text-sm font-bold text-accent-600">
            {resolvedGaps} / {totalGaps} resolved ({progressPct}%)
          </span>
        </div>
        <div className="h-3 bg-stone-200 rounded-full overflow-hidden shadow-inner">
          <div
            className="h-full rounded-full transition-all duration-500 ease-out"
            style={{
              width: `${progressPct}%`,
              background: progressPct === 100
                ? 'linear-gradient(90deg, #10b981, #34d399)'
                : 'linear-gradient(90deg, #ea580c, #fb923c)',
            }}
          />
        </div>
        <div className="flex gap-4 mt-4 text-xs font-semibold text-stone-600">
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block shadow-sm" /> Accepted: {gaps.filter(g => g.status === 'accepted').length}</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-orange-500 inline-block shadow-sm" /> Remediation: {gaps.filter(g => g.status === 'remediation').length}</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block shadow-sm" /> Exemption: {gaps.filter(g => g.status === 'exemption').length}</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-stone-300 inline-block shadow-sm" /> Open: {gaps.filter(g => g.status === 'open').length}</span>
        </div>
      </div>

      {/* Gap Rows */}
      <div className="space-y-3">
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
                'rounded-xl border transition-all duration-200',
                statusCfg.border,
                statusCfg.bg
              )}
            >
              {/* Main Row */}
              <div className="flex items-center gap-4 p-5">
                {/* Category Badge */}
                <span className={clsx('flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider w-20 shrink-0', catCfg.color)}>
                  {catCfg.icon} {catCfg.label}
                </span>

                {/* Gap Text */}
                <p className="flex-1 text-sm text-stone-800 leading-relaxed font-medium">{gap.text}</p>

                {/* Status Selector */}
                <select
                  value={gap.status}
                  onChange={(e) => handleStatusChange(gap, e.target.value as GapStatus)}
                  disabled={isSaving}
                  className={clsx(
                    'text-xs font-bold uppercase px-3 py-2 rounded-lg border cursor-pointer transition-colors shadow-sm',
                    'bg-white focus:outline-none focus:ring-2 focus:ring-accent-500/20',
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
                  className="text-stone-400 hover:text-stone-700 transition-colors p-2 rounded-lg hover:bg-stone-200/50"
                  title="Add internal note"
                >
                  <MessageSquare size={16} />
                  {isExpanded ? <ChevronUp size={14} className="mt-1" /> : <ChevronDown size={14} className="mt-1" />}
                </button>
              </div>

              {/* Collapsible Note Area */}
              {isExpanded && (
                <div className="px-5 pb-5 pt-0 border-t border-black/5 mt-2">
                  <div className="flex items-center gap-4 mb-2 mt-4">
                    <label className="text-[11px] font-semibold text-stone-500 uppercase tracking-widest flex items-center gap-1.5">
                      <User size={14} /> Assign To
                    </label>
                  </div>
                  <div className="flex gap-3 flex-col sm:flex-row">
                    <select
                      value={assignedInputs[key] !== undefined ? assignedInputs[key] : (gap.assigned_to || '')}
                      onChange={(e) => setAssignedInputs(prev => ({ ...prev, [key]: e.target.value }))}
                      className="bg-white border border-stone-200 rounded-xl px-4 py-2 text-sm text-stone-700 focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 font-medium sm:w-56 shadow-sm"
                    >
                      <option value="">-- Unassigned --</option>
                      {employees.map(emp => (
                        <option key={emp.id} value={emp.id}>{emp.name} ({emp.position})</option>
                      ))}
                    </select>
                    
                    <input
                      type="text"
                      value={noteInputs[key] ?? gap.note}
                      onChange={(e) => setNoteInputs(prev => ({ ...prev, [key]: e.target.value }))}
                      placeholder="Write-off reason or internal note..."
                      className="flex-1 bg-white border border-stone-200 rounded-xl px-4 py-2 text-sm text-stone-700 focus:outline-none focus:border-accent-500 focus:ring-2 focus:ring-accent-500/20 font-medium shadow-sm"
                    />
                    <button
                      onClick={() => handleSaveNote(gap)}
                      disabled={isSaving}
                      className="bg-stone-800 hover:bg-stone-900 text-white text-xs font-bold uppercase tracking-wider px-5 py-2 rounded-xl transition-colors disabled:opacity-50 shadow-sm"
                    >
                      {isSaving ? '...' : 'Save'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
