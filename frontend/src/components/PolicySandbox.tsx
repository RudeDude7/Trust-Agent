import React, { useState } from 'react';
import type { SavedAudit, RiskAssessment } from '../types';
import { Beaker, Play, Loader, ShieldAlert, ShieldCheck, ArrowRight, RotateCcw } from 'lucide-react';
import { evaluateSandbox } from '../api';
import clsx from 'clsx';

interface PolicySandboxProps {
  data: SavedAudit;
}

export const PolicySandbox: React.FC<PolicySandboxProps> = ({ data }) => {
  const { risk_assessment, session_id } = data;
  
  // We only care about internal clauses because those are the "rules" we can toggle off.
  const allInternalClauses = risk_assessment.raw_rag_clauses?.filter(c => c.role === 'internal') || [];
  
  const [disabledClauses, setDisabledClauses] = useState<Set<string>>(new Set());
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulatedRisk, setSimulatedRisk] = useState<RiskAssessment | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (allInternalClauses.length === 0) {
    return (
      <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-8 text-center mt-8">
        <Beaker className="mx-auto text-slate-500 mb-4" size={32} />
        <h3 className="text-lg font-bold text-slate-300 font-mono mb-2">Sandbox Unavailable</h3>
        <p className="text-sm text-slate-400">
          This audit is either too old or did not parse any internal policies. 
          Please re-run the vendor analysis with an internal policy document uploaded to enable "What-If" simulations.
        </p>
      </div>
    );
  }

  const toggleClause = (clauseText: string) => {
    setDisabledClauses(prev => {
      const next = new Set(prev);
      if (next.has(clauseText)) next.delete(clauseText);
      else next.add(clauseText);
      return next;
    });
  };

  const handleSimulate = async () => {
    try {
      setIsSimulating(true);
      setError(null);
      const result = await evaluateSandbox(session_id, Array.from(disabledClauses));
      setSimulatedRisk(result);
    } catch (err: any) {
      setError(err.message || 'Simulation failed.');
    } finally {
      setIsSimulating(false);
    }
  };

  const resetSandbox = () => {
    setDisabledClauses(new Set());
    setSimulatedRisk(null);
  };

  return (
    <div className="mt-8">
      <div className="flex items-center gap-3 mb-6">
        <Beaker className="text-fuchsia-500" size={24} />
        <h2 className="text-xl font-bold font-mono tracking-tight text-slate-200">
          Policy Sandbox ("What-If" Analysis)
        </h2>
      </div>

      <p className="text-sm text-slate-400 mb-6 leading-relaxed">
        Dynamically toggle internal security requirements on or off to simulate how the vendor's risk score would change if a specific internal policy exception was granted.
      </p>

      <div className="grid md:grid-cols-2 gap-8">
        
        {/* Left Column: Toggles */}
        <div className="bg-slate-800/20 border border-slate-700/50 rounded-xl p-6">
          <h3 className="text-sm font-mono font-bold text-slate-300 uppercase tracking-widest mb-4 flex items-center justify-between">
            <span>Internal Policy Requirements</span>
            <button onClick={resetSandbox} className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1 transition-colors">
              <RotateCcw size={12} /> Reset
            </button>
          </h3>
          <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
            {allInternalClauses.map((clause, idx) => {
              const isDisabled = disabledClauses.has(clause.clause_text);
              return (
                <div 
                  key={idx}
                  onClick={() => toggleClause(clause.clause_text)}
                  className={clsx(
                    "p-4 rounded-lg border text-sm cursor-pointer transition-all flex items-start gap-3",
                    isDisabled 
                      ? "bg-slate-800/50 border-slate-700/50 opacity-50" 
                      : "bg-fuchsia-900/10 border-fuchsia-500/30 hover:border-fuchsia-500/60"
                  )}
                >
                  <div className="mt-0.5">
                    <input 
                      type="checkbox" 
                      checked={!isDisabled}
                      onChange={() => {}} // handled by parent onClick
                      className="accent-fuchsia-500 w-4 h-4"
                    />
                  </div>
                  <div className={clsx("flex-1", isDisabled ? "text-slate-500 line-through" : "text-slate-300")}>
                    {clause.clause_text}
                  </div>
                </div>
              );
            })}
          </div>
          
          <button
            onClick={handleSimulate}
            disabled={isSimulating || disabledClauses.size === 0}
            className="w-full mt-6 bg-fuchsia-600 hover:bg-fuchsia-500 text-white py-3 rounded-lg font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSimulating ? <Loader className="animate-spin" size={18} /> : <Play size={18} fill="currentColor" />}
            {isSimulating ? 'SIMULATING...' : `SIMULATE WITH ${disabledClauses.size} EXCEPTION${disabledClauses.size === 1 ? '' : 'S'}`}
          </button>
          {error && <p className="text-red-400 text-xs mt-3 text-center">{error}</p>}
        </div>

        {/* Right Column: Simulation Results */}
        <div className="bg-slate-800/20 border border-slate-700/50 rounded-xl p-6 flex flex-col">
          <h3 className="text-sm font-mono font-bold text-slate-300 uppercase tracking-widest mb-4">
            Simulated Outcome
          </h3>

          {!simulatedRisk ? (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
              <Beaker size={48} className="mb-4 opacity-20" />
              <p className="text-sm text-center max-w-xs">Select policy exceptions and run the simulation to see the hypothetical risk assessment.</p>
            </div>
          ) : (
            <div className="flex-1 flex flex-col animate-in fade-in zoom-in duration-300">
              
              {/* Score Comparison */}
              <div className="flex items-center justify-center gap-6 mb-8 mt-4">
                <div className="text-center">
                  <div className="text-xs font-mono text-slate-500 uppercase tracking-widest mb-1">Original</div>
                  <div className={clsx(
                    "text-2xl font-black",
                    ['HIGH', 'CRITICAL'].includes(risk_assessment.overall_risk_level) ? "text-red-500" : "text-emerald-500"
                  )}>
                    {risk_assessment.overall_risk_level}
                  </div>
                </div>
                
                <ArrowRight className="text-slate-600" size={24} />
                
                <div className="text-center">
                  <div className="text-xs font-mono text-fuchsia-400 uppercase tracking-widest mb-1">Simulated</div>
                  <div className={clsx(
                    "text-3xl font-black",
                    ['HIGH', 'CRITICAL'].includes(simulatedRisk.overall_risk_level) ? "text-red-500" : "text-emerald-500"
                  )}>
                    {simulatedRisk.overall_risk_level}
                  </div>
                </div>
              </div>

              {/* RAG Changes */}
              <div className="flex-1">
                 <h4 className="text-xs font-mono font-bold text-indigo-400 uppercase tracking-widest mb-3">Simulated RAG Inferences</h4>
                 {simulatedRisk.rag_inferences.length === 0 ? (
                   <div className="bg-emerald-900/10 border border-emerald-500/20 rounded p-4 flex gap-3 text-emerald-400 text-sm">
                     <ShieldCheck size={18} />
                     <span>No policy discrepancies remain!</span>
                   </div>
                 ) : (
                   <ul className="space-y-3">
                     {simulatedRisk.rag_inferences.map((inf, idx) => (
                       <li key={idx} className="flex gap-3 text-sm text-slate-300 bg-slate-800/50 p-3 rounded border border-slate-700/50">
                         <span className="text-indigo-400 font-mono mt-0.5">[{idx + 1}]</span>
                         <span>{inf}</span>
                       </li>
                     ))}
                   </ul>
                 )}
              </div>

            </div>
          )}
        </div>

      </div>
    </div>
  );
};
