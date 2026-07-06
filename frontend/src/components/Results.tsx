import React from 'react';
import type { SavedAudit } from '../types';
import { ShieldAlert, ShieldCheck, Activity, FileText, Target, AlertTriangle, Send, Loader, Copy, Check, ClipboardList, Eye, EyeOff } from 'lucide-react';
import { generateRemediation, watchVendor, unwatchVendor, fetchWatchedVendors } from '../api';
import { GapMatrix } from './GapMatrix';
import { ExecutiveReport } from './ExecutiveReport';
import { PolicySandbox } from './PolicySandbox';
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
  const [isWatching, setIsWatching] = React.useState(false);
  const [isWatchLoading, setIsWatchLoading] = React.useState(false);

  // Strip (vX) or other version tags from the vendor name for watching
  const baseVendorName = vendor_name.replace(/\s*\(.*\)\s*/g, '').trim();

  React.useEffect(() => {
    fetchWatchedVendors().then(vendors => {
      setIsWatching(vendors.some(v => v.vendor_name === baseVendorName));
    }).catch(console.error);
  }, [baseVendorName]);

  const handleToggleWatch = async () => {
    try {
      setIsWatchLoading(true);
      if (isWatching) {
        await unwatchVendor(baseVendorName);
        setIsWatching(false);
      } else {
        await watchVendor(baseVendorName);
        setIsWatching(true);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsWatchLoading(false);
    }
  };

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
    <div className="flex flex-col p-8 gap-8 text-stone-800 min-h-full max-w-6xl mx-auto w-full pb-32">
      
      {/* Header Panel */}
      <div className={clsx(
        "rounded-3xl border p-8 shadow-soft",
        isHighRisk ? "bg-red-50/50 border-red-200" : "bg-emerald-50/50 border-emerald-200"
      )}>
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
          <div className="flex-1">
            <h1 className="text-4xl font-bold font-heading tracking-tight flex items-center gap-3 text-stone-900">
              {vendor_name}
              {isHighRisk ? <ShieldAlert className="text-red-500" size={32} /> : <ShieldCheck className="text-emerald-500" size={32} />}
            </h1>
            <p className="mt-4 text-lg text-stone-600 leading-relaxed max-w-4xl">
              {risk_assessment.summary}
            </p>
          </div>
          <div className="text-right flex flex-col items-end shrink-0">
            <span className="text-sm font-semibold text-stone-500 uppercase tracking-widest mb-1">Risk Level</span>
            <span className={clsx(
              "text-5xl font-heading font-bold tracking-tighter",
              isHighRisk ? "text-red-600" : "text-emerald-600"
            )}>
              {risk_assessment.overall_risk_level}
            </span>
            <span className="text-xs font-semibold text-stone-400 mt-2 mb-4 bg-stone-100 px-2 py-1 rounded-md">CONFIDENCE: {(risk_assessment.confidence_score * 100).toFixed(0)}%</span>
            
            <button
              onClick={handleToggleWatch}
              disabled={isWatchLoading}
              className={clsx(
                "text-xs font-semibold px-4 py-2 rounded-xl flex items-center gap-2 transition-all border shadow-sm",
                isWatching 
                  ? "bg-accent-50 text-accent-700 border-accent-200 hover:bg-accent-100" 
                  : "bg-white text-stone-600 border-stone-200 hover:bg-stone-50 hover:text-stone-800",
                isWatchLoading && "opacity-50 cursor-not-allowed"
              )}
            >
              {isWatching ? <Eye size={16} /> : <EyeOff size={16} />}
              {isWatching ? "Watching" : "Watch Vendor"}
            </button>
          </div>
        </div>
      </div>

      {/* Synthesis / Comparative Analysis & Remediation Action */}
      <div className="grid md:grid-cols-3 gap-8 items-stretch">
        <div className="md:col-span-2 flex flex-col h-full bg-white border border-stone-200 rounded-3xl p-8 shadow-soft">
          <h2 className="text-sm font-semibold text-accent-600 uppercase tracking-widest flex items-center gap-2 mb-4">
            <Target size={18} /> Synthesis & Comparative Analysis
          </h2>
          <div className="bg-stone-50 border border-stone-100 rounded-2xl p-6 text-stone-700 leading-relaxed flex-1">
            {risk_assessment.comparative_analysis}
          </div>
        </div>
        <div className="md:col-span-1 flex flex-col h-full justify-start bg-white border border-stone-200 rounded-3xl p-8 shadow-soft">
           <h2 className="text-sm font-semibold text-accent-600 uppercase tracking-widest flex items-center gap-2 mb-4">
             Actionable Remediation
           </h2>
           <div className="bg-stone-50 border border-stone-100 rounded-2xl p-6 flex-1 flex flex-col items-center justify-center text-center gap-5">
              <div className="text-stone-500 text-sm">
                Generate a professional email addressed to the vendor's security team requesting remediation.
              </div>
              <button
                onClick={handleGenerate}
                disabled={isGenerating || remediationDraft !== null}
                className="w-full bg-stone-800 hover:bg-stone-900 text-white py-3.5 rounded-xl font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              >
                {isGenerating ? <Loader className="animate-spin" size={18} /> : <Send size={18} />}
                {isGenerating ? "Drafting..." : "Generate Request"}
              </button>
              
              <div className="w-full h-px bg-stone-200 my-2"></div>
              
              <div className="text-stone-500 text-sm">
                Download a clean, CISO-ready PDF executive briefing summarizing these findings.
              </div>
              <div className="w-full">
                <ExecutiveReport data={data} />
              </div>
              
              {generateError && <p className="text-red-500 text-xs mt-2">{generateError}</p>}
           </div>
        </div>
      </div>

      {/* Generated Draft View */}
      {remediationDraft && (
        <div className="bg-white border border-stone-200 rounded-3xl p-8 shadow-soft">
           <div className="flex items-center justify-between mb-4">
             <h2 className="text-sm font-semibold text-accent-600 uppercase tracking-widest flex items-center gap-2">
                <FileText size={18} /> Remediation Email Draft
             </h2>
             <button onClick={handleCopy} className="text-xs bg-stone-100 hover:bg-stone-200 px-4 py-2 rounded-xl flex items-center gap-2 font-semibold text-stone-700 transition-colors shadow-sm">
               {copied ? <Check size={14} className="text-emerald-600" /> : <Copy size={14} />}
               {copied ? "Copied!" : "Copy to Clipboard"}
             </button>
           </div>
           <textarea
             readOnly
             className="w-full h-64 bg-stone-50 border border-stone-200 rounded-2xl p-6 text-stone-700 focus:outline-none focus:border-accent-500 font-sans leading-relaxed resize-y"
             value={remediationDraft}
           />
        </div>
      )}

      {/* Bifurcated Inferences */}
      <div className="grid md:grid-cols-2 gap-8">
        
        {/* OSINT Panel */}
        <div className="flex flex-col h-full bg-white border border-stone-200 rounded-3xl p-8 shadow-soft">
          <h2 className="text-sm font-semibold text-orange-500 uppercase tracking-widest flex items-center gap-2 mb-4">
            <Activity size={18} /> External Recon (OSINT)
          </h2>
          <div className="bg-stone-50 border border-stone-100 rounded-2xl p-6 flex-1">
            {risk_assessment.osint_inferences.length === 0 ? (
              <p className="text-stone-400 italic text-sm">No significant external risks found.</p>
            ) : (
              <ul className="space-y-4">
                {risk_assessment.osint_inferences.map((inf, idx) => (
                  <li key={idx} className="flex gap-3 text-sm text-stone-700">
                    <span className="text-orange-500 font-semibold mt-0.5">[{idx + 1}]</span>
                    <span>{inf}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* RAG Panel */}
        <div className="flex flex-col h-full bg-white border border-stone-200 rounded-3xl p-8 shadow-soft">
          <h2 className="text-sm font-semibold text-accent-600 uppercase tracking-widest flex items-center gap-2 mb-4">
            <FileText size={18} /> Policy Comparison (RAG)
          </h2>
          <div className="bg-stone-50 border border-stone-100 rounded-2xl p-6 flex-1">
            {risk_assessment.rag_inferences.length === 0 ? (
              <p className="text-stone-400 italic text-sm">No policy discrepancies identified.</p>
            ) : (
              <ul className="space-y-4">
                {risk_assessment.rag_inferences.map((inf, idx) => (
                  <li key={idx} className="flex gap-3 text-sm text-stone-700">
                    <span className="text-accent-600 font-semibold mt-0.5">[{idx + 1}]</span>
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
        <div className="bg-white border border-stone-200 rounded-3xl p-8 shadow-soft">
          <h2 className="text-sm font-semibold text-stone-500 uppercase tracking-widest flex items-center gap-2 mb-4">
            <AlertTriangle size={18} /> Intelligence Gaps
          </h2>
          <div className="bg-stone-50 border border-stone-100 rounded-2xl p-6">
            <ul className="space-y-2">
              {risk_assessment.data_gaps.map((gap, idx) => (
                <li key={idx} className="flex gap-2 text-sm text-stone-600">
                  <span className="text-stone-400">-</span>
                  {gap}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Interactive Compliance Gap Matrix */}
      <div className="bg-white border border-stone-200 rounded-3xl p-8 shadow-soft">
        <h2 className="text-sm font-semibold text-accent-600 uppercase tracking-widest flex items-center gap-2 mb-6">
          <ClipboardList size={18} /> Compliance Gap Matrix
        </h2>
        <GapMatrix data={data} />
      </div>

      {/* Policy Sandbox */}
      <div className="bg-white border border-stone-200 rounded-3xl p-8 shadow-soft">
        <PolicySandbox data={data} />
      </div>

    </div>
  );
};
