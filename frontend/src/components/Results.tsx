import React from 'react';
import type { AnalysisResponse } from '../types';
import { ShieldAlert, ShieldCheck, Activity, FileText, Target, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';

interface ResultsProps {
  data: AnalysisResponse;
}

export const Results: React.FC<ResultsProps> = ({ data }) => {
  const { risk_assessment, vendor } = data;
  const isHighRisk = risk_assessment.overall_risk_level === 'HIGH' || risk_assessment.overall_risk_level === 'CRITICAL';

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
              {vendor}
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

      {/* Synthesis / Comparative Analysis */}
      <div className="mb-8">
        <h2 className="text-sm font-mono font-bold text-cyan-400 uppercase tracking-widest flex items-center gap-2 mb-3">
          <Target size={16} /> Synthesis & Comparative Analysis
        </h2>
        <div className="bg-slate-800/50 border border-cyan-900/50 rounded-xl p-6 text-slate-300 leading-relaxed">
          {risk_assessment.comparative_analysis}
        </div>
      </div>

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

    </div>
  );
};
