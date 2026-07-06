import React, { useState } from 'react';
import type { SavedAudit, RiskAssessment } from '../types';
import { Beaker, Play, Loader, ShieldCheck, ArrowRight, RotateCcw } from 'lucide-react';
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
      <div className="bg-stone-50 border border-stone-200 rounded-2xl p-8 text-center mt-8 shadow-sm">
        <Beaker className="mx-auto text-stone-400 mb-4" size={32} />
        <h3 className="text-lg font-bold text-stone-700 font-heading mb-2">Sandbox Unavailable</h3>
        <p className="text-sm text-stone-500 max-w-md mx-auto">
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
    <div>
      <div className="flex items-center gap-3 mb-4">
        <Beaker className="text-accent-600" size={24} />
        <h2 className="text-xl font-bold font-heading tracking-tight text-stone-900">
          Policy Sandbox ("What-If" Analysis)
        </h2>
      </div>

      <p className="text-sm text-stone-500 mb-8 leading-relaxed max-w-3xl">
        Dynamically toggle internal security requirements on or off to simulate how the vendor's risk score would change if a specific internal policy exception was granted.
      </p>

      <div className="grid md:grid-cols-2 gap-8">
        
        {/* Left Column: Toggles */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-soft">
          <h3 className="text-sm font-semibold text-stone-500 uppercase tracking-widest mb-6 flex items-center justify-between">
            <span>Internal Policy Requirements</span>
            <button onClick={resetSandbox} className="text-xs font-bold text-stone-400 hover:text-stone-700 flex items-center gap-1.5 transition-colors bg-stone-50 hover:bg-stone-100 px-2 py-1 rounded-md border border-stone-200">
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
                    "p-4 rounded-xl border text-sm cursor-pointer transition-all flex items-start gap-3 shadow-sm hover:shadow-soft",
                    isDisabled 
                      ? "bg-stone-50 border-stone-200 opacity-60" 
                      : "bg-white border-accent-200 hover:border-accent-400"
                  )}
                >
                  <div className="mt-0.5">
                    <input 
                      type="checkbox" 
                      checked={!isDisabled}
                      onChange={() => {}} // handled by parent onClick
                      className="accent-accent-600 w-4 h-4 cursor-pointer"
                    />
                  </div>
                  <div className={clsx("flex-1 font-medium", isDisabled ? "text-stone-400 line-through" : "text-stone-700")}>
                    {clause.clause_text}
                  </div>
                </div>
              );
            })}
          </div>
          
          <button
            onClick={handleSimulate}
            disabled={isSimulating || disabledClauses.size === 0}
            className="w-full mt-6 bg-accent-600 hover:bg-accent-700 text-white py-3.5 rounded-xl font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            {isSimulating ? <Loader className="animate-spin" size={18} /> : <Play size={18} fill="currentColor" />}
            {isSimulating ? 'SIMULATING...' : `SIMULATE WITH ${disabledClauses.size} EXCEPTION${disabledClauses.size === 1 ? '' : 'S'}`}
          </button>
          {error && <p className="text-red-500 font-medium text-xs mt-3 text-center">{error}</p>}
        </div>

        {/* Right Column: Simulation Results */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 flex flex-col shadow-soft">
          <h3 className="text-sm font-semibold text-stone-500 uppercase tracking-widest mb-6">
            Simulated Outcome
          </h3>

          {!simulatedRisk ? (
            <div className="flex-1 flex flex-col items-center justify-center text-stone-400">
              <Beaker size={48} className="mb-4 text-stone-200" />
              <p className="text-sm text-center max-w-xs font-medium">Select policy exceptions and run the simulation to see the hypothetical risk assessment.</p>
            </div>
          ) : (
            <div className="flex-1 flex flex-col animate-in fade-in zoom-in duration-300">
              
              {/* Score Comparison */}
              <div className="flex items-center justify-center gap-8 mb-10 mt-4 bg-stone-50 rounded-2xl py-6 border border-stone-100">
                <div className="text-center">
                  <div className="text-xs font-bold text-stone-400 uppercase tracking-widest mb-2">Original</div>
                  <div className={clsx(
                    "text-2xl font-black font-heading tracking-tight",
                    ['HIGH', 'CRITICAL'].includes(risk_assessment.overall_risk_level) ? "text-red-500" : "text-emerald-500"
                  )}>
                    {risk_assessment.overall_risk_level}
                  </div>
                </div>
                
                <ArrowRight className="text-stone-300" size={24} />
                
                <div className="text-center">
                  <div className="text-xs font-bold text-accent-500 uppercase tracking-widest mb-2">Simulated</div>
                  <div className={clsx(
                    "text-3xl font-black font-heading tracking-tight",
                    ['HIGH', 'CRITICAL'].includes(simulatedRisk.overall_risk_level) ? "text-red-600" : "text-emerald-600"
                  )}>
                    {simulatedRisk.overall_risk_level}
                  </div>
                </div>
              </div>

              {/* RAG Changes */}
              <div className="flex-1">
                 <h4 className="text-xs font-bold text-accent-600 uppercase tracking-widest mb-4">Simulated RAG Inferences</h4>
                 {simulatedRisk.rag_inferences.length === 0 ? (
                   <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex gap-3 text-emerald-700 font-medium text-sm shadow-sm">
                     <ShieldCheck size={18} className="text-emerald-500" />
                     <span>No policy discrepancies remain!</span>
                   </div>
                 ) : (
                   <ul className="space-y-3">
                     {simulatedRisk.rag_inferences.map((inf, idx) => (
                       <li key={idx} className="flex gap-3 text-sm text-stone-700 bg-white p-4 rounded-xl border border-stone-200 shadow-sm font-medium">
                         <span className="text-accent-500 font-bold mt-0.5">[{idx + 1}]</span>
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
