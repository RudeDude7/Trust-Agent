import React from 'react';
import type { SavedAudit } from '../types';
import { ShieldAlert, ShieldCheck, Activity, FileText, Target, AlertTriangle, Send, Loader, Copy, Check, ClipboardList } from 'lucide-react';
import { generateRemediation } from '../api';
import { GapMatrix } from './GapMatrix';
import clsx from 'clsx';

interface ResultsProps {
  data: SavedAudit;
}

export const Results: React.FC<ResultsProps> = ({ data }) => {
  const { risk_assessment, vendor_name, session_id } = data;
  const isHighRisk = risk_assessment.overall_risk_level === 'HIGH' || risk_assessment.overall_risk_level === 'CRITICAL';

  const [isGenerating, setIsGenerating] = React.useState(false);
  const [remediationDraft, setRemediationDraft] = React.useState<string | null>(null);
  const [copied, setCopied] = React.useState(false);
  const [generateError, setGenerateError] = React.useState<string | null>(null);

  const handleGenerate = async () => {
    try {
      setIsGenerating(true);
      setGenerateError(null);
      const draft = await generateRemediation(session_id);
      setRemediationDraft(draft);
    } catch (err: any) {
      setGenerateError(err.message || 'Failed to generate draft');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopy = () => {
    if (remediationDraft) {
      navigator.clipboard.writeText(remediationDraft);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto bg-slate-900 p-8 text-slate-200">
      
      {/* Header Panel */}
      <div className={clsx(
        "rounded-xl border p-6 mb-8 shadow-lg",
        isHighRisk ? "bg-red-900/10 border-red-500/50" : "bg-emerald-900/10 border-emerald-500/50"
      )}>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold font-mono tracking-tight flex items-center gap-3">
              {vendor_name}
              {isHighRisk ? <ShieldAlert className="text-red-500" size={32} /> : <ShieldCheck className="text-emerald-500" size={32} />}
            </h1>
            <p className="mt-4 text-lg text-slate-300 leading-relaxed max-w-4xl">
              {risk_assessment.summary}
            </p>
          </div>
          <div className="text-right flex flex-col items-end">
            <span className="text-sm font-mono text-slate-500 uppercase tracking-widest mb-1">Risk Level</span>
            <span className={clsx(
              "text-4xl font-black tracking-tighter",
              isHighRisk ? "text-red-500" : "text-emerald-500"
            )}>
              {risk_assessment.overall_risk_level}
            </span>
            <span className="text-xs font-mono text-slate-500 mt-2">CONFIDENCE: {(risk_assessment.confidence_score * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>

      {/* Synthesis / Comparative Analysis & Remediation Action */}
      <div className="mb-8 grid md:grid-cols-3 gap-6">
        <div className="md:col-span-2">
          <h2 className="text-sm font-mono font-bold text-cyan-400 uppercase tracking-widest flex items-center gap-2 mb-3">
            <Target size={16} /> Synthesis & Comparative Analysis
          </h2>
          <div className="bg-slate-800/50 border border-cyan-900/50 rounded-xl p-6 text-slate-300 leading-relaxed h-full">
            {risk_assessment.comparative_analysis}
          </div>
        </div>
        <div className="md:col-span-1 flex flex-col justify-center">
           <h2 className="text-sm font-mono font-bold text-indigo-400 uppercase tracking-widest flex items-center gap-2 mb-3">
             Actionable Remediation
           </h2>
           <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6 flex-1 flex flex-col items-center justify-center text-center gap-4">
              <div className="text-slate-400 text-sm">
                Generate a professional email addressed to the vendor's security team requesting remediation for the identified gaps.
              </div>
              <button
                onClick={handleGenerate}
                disabled={isGenerating || remediationDraft !== null}
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-3 rounded-lg font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isGenerating ? <Loader className="animate-spin" size={18} /> : <Send size={18} />}
                {isGenerating ? "DRAFTING..." : "GENERATE REQUEST"}
              </button>
              {generateError && <p className="text-red-400 text-xs mt-2">{generateError}</p>}
           </div>
        </div>
      </div>

      {/* Generated Draft View */}
      {remediationDraft && (
        <div className="mb-8 relative">
           <div className="flex items-center justify-between mb-3">
             <h2 className="text-sm font-mono font-bold text-indigo-400 uppercase tracking-widest flex items-center gap-2">
                <FileText size={16} /> Remediation Email Draft
             </h2>
             <button onClick={handleCopy} className="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded flex items-center gap-1 font-mono text-slate-200 transition-colors">
               {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
               {copied ? "COPIED!" : "COPY TO CLIPBOARD"}
             </button>
           </div>
           <textarea
             readOnly
             className="w-full h-64 bg-slate-800 border border-indigo-500/30 rounded-xl p-6 text-slate-300 focus:outline-none focus:border-indigo-500 font-sans leading-relaxed resize-y"
             value={remediationDraft}
           />
        </div>
      )}

      {/* Bifurcated Inferences */}
      <div className="grid md:grid-cols-2 gap-8 mb-8">
        
        {/* OSINT Panel */}
        <div className="flex flex-col h-full">
          <h2 className="text-sm font-mono font-bold text-amber-500 uppercase tracking-widest flex items-center gap-2 mb-3">
            <Activity size={16} /> External Recon (OSINT)
          </h2>
          <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6 flex-1">
            {risk_assessment.osint_inferences.length === 0 ? (
              <p className="text-slate-500 italic text-sm">No significant external risks found.</p>
            ) : (
              <ul className="space-y-4">
                {risk_assessment.osint_inferences.map((inf, idx) => (
                  <li key={idx} className="flex gap-3 text-sm text-slate-300">
                    <span className="text-amber-500 font-mono mt-0.5">[{idx + 1}]</span>
                    <span>{inf}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* RAG Panel */}
        <div className="flex flex-col h-full">
          <h2 className="text-sm font-mono font-bold text-indigo-400 uppercase tracking-widest flex items-center gap-2 mb-3">
            <FileText size={16} /> Policy Comparison (RAG)
          </h2>
          <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-6 flex-1">
            {risk_assessment.rag_inferences.length === 0 ? (
              <p className="text-slate-500 italic text-sm">No policy discrepancies identified.</p>
            ) : (
              <ul className="space-y-4">
                {risk_assessment.rag_inferences.map((inf, idx) => (
                  <li key={idx} className="flex gap-3 text-sm text-slate-300">
                    <span className="text-indigo-400 font-mono mt-0.5">[{idx + 1}]</span>
                    <span>{inf}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

      </div>

      {/* Data Gaps */}
      {risk_assessment.data_gaps.length > 0 && (
        <div>
          <h2 className="text-sm font-mono font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2 mb-3">
            <AlertTriangle size={16} /> Intelligence Gaps
          </h2>
          <div className="bg-slate-800/20 border border-slate-800 rounded-xl p-6">
            <ul className="space-y-2">
              {risk_assessment.data_gaps.map((gap, idx) => (
                <li key={idx} className="flex gap-2 text-sm text-slate-400">
                  <span className="text-slate-600">-</span>
                  {gap}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Interactive Compliance Gap Matrix */}
      <div className="mt-8 border-t border-slate-800 pt-8">
        <h2 className="text-sm font-mono font-bold text-cyan-400 uppercase tracking-widest flex items-center gap-2 mb-6">
          <ClipboardList size={16} /> Compliance Gap Matrix
        </h2>
        <GapMatrix data={data} />
      </div>

    </div>
  );
};
