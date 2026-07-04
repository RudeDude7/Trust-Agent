import React, { useRef, useState } from 'react';
import type { SavedAudit, GapAction } from '../types';
import { Download, Loader } from 'lucide-react';

interface ExecutiveReportProps {
  data: SavedAudit;
}

const RISK_COLORS: Record<string, string> = {
  LOW: '#10b981',
  MEDIUM: '#f59e0b',
  HIGH: '#ef4444',
  CRITICAL: '#dc2626',
};

const RISK_ANGLES: Record<string, number> = {
  LOW: -60,
  MEDIUM: -20,
  HIGH: 20,
  CRITICAL: 60,
};

const RiskDial: React.FC<{ level: string; confidence: number }> = ({ level, confidence }) => {
  const color = RISK_COLORS[level] || '#94a3b8';
  const angle = RISK_ANGLES[level] ?? 0;

  return (
    <svg viewBox="0 0 200 120" width="200" height="120" style={{ display: 'block', margin: '0 auto' }}>
      {/* Background arc */}
      <path
        d="M 20 100 A 80 80 0 0 1 180 100"
        fill="none"
        stroke="#334155"
        strokeWidth="14"
        strokeLinecap="round"
      />
      {/* Colored segments */}
      <path d="M 20 100 A 80 80 0 0 1 55 35" fill="none" stroke="#10b981" strokeWidth="14" strokeLinecap="round" />
      <path d="M 55 35 A 80 80 0 0 1 100 20" fill="none" stroke="#f59e0b" strokeWidth="14" strokeLinecap="round" />
      <path d="M 100 20 A 80 80 0 0 1 145 35" fill="none" stroke="#ef4444" strokeWidth="14" strokeLinecap="round" />
      <path d="M 145 35 A 80 80 0 0 1 180 100" fill="none" stroke="#dc2626" strokeWidth="14" strokeLinecap="round" />
      {/* Needle */}
      <line
        x1="100"
        y1="100"
        x2={100 + 55 * Math.cos(((angle - 90) * Math.PI) / 180)}
        y2={100 + 55 * Math.sin(((angle - 90) * Math.PI) / 180)}
        stroke={color}
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle cx="100" cy="100" r="6" fill={color} />
      {/* Label */}
      <text x="100" y="115" textAnchor="middle" fontSize="11" fontWeight="bold" fill={color} fontFamily="monospace">
        {level}
      </text>
    </svg>
  );
};

export const ExecutiveReport: React.FC<ExecutiveReportProps> = ({ data }) => {
  const reportRef = useRef<HTMLDivElement>(null);
  const [isExporting, setIsExporting] = useState(false);
  const { risk_assessment, vendor_name, created_at } = data;

  const gapActions: GapAction[] = risk_assessment.gap_actions || [];
  const totalGaps = risk_assessment.osint_inferences.length + risk_assessment.rag_inferences.length + risk_assessment.data_gaps.length;
  const resolvedGaps = gapActions.filter(a => a.status !== 'open').length;

  const recommendation = (() => {
    switch (risk_assessment.overall_risk_level) {
      case 'LOW': return { text: 'APPROVE — Vendor meets all internal security standards.', color: '#10b981' };
      case 'MEDIUM': return { text: 'CONDITIONALLY APPROVE — Minor gaps identified, remediation recommended before full onboarding.', color: '#f59e0b' };
      case 'HIGH': return { text: 'ESCALATE — Significant risks detected. Vendor requires remediation plan before approval.', color: '#ef4444' };
      case 'CRITICAL': return { text: 'REJECT — Critical security risks identified. Do not proceed with vendor engagement.', color: '#dc2626' };
      default: return { text: 'REVIEW REQUIRED', color: '#94a3b8' };
    }
  })();

  const handleExport = async () => {
    if (!reportRef.current) return;
    setIsExporting(true);

    try {
      // Dynamic import to avoid SSR issues
      const html2pdf = (await import('html2pdf.js')).default;

      const opt = {
        margin: [10, 10, 10, 10],
        filename: `Trust_Agent_Executive_Briefing_${vendor_name.replace(/\s+/g, '_')}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' as const },
      };

      await html2pdf().set(opt).from(reportRef.current).save();
    } catch (err) {
      console.error('PDF export failed:', err);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div>
      {/* Export Button */}
      <button
        onClick={handleExport}
        disabled={isExporting}
        className="w-full bg-emerald-700 hover:bg-emerald-600 text-white py-3 rounded-lg font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isExporting ? <Loader className="animate-spin" size={18} /> : <Download size={18} />}
        {isExporting ? 'GENERATING PDF...' : 'EXPORT EXECUTIVE BRIEFING'}
      </button>

      {/* Hidden Report Layout (rendered off-screen for html2pdf) */}
      <div style={{ position: 'absolute', left: '-9999px', top: 0, width: '700px' }}>
        <div ref={reportRef} style={{ padding: '40px', fontFamily: "'Segoe UI', Arial, sans-serif", color: '#1e293b', backgroundColor: '#ffffff' }}>

          {/* Header */}
          <div style={{ borderBottom: '3px solid #0891b2', paddingBottom: '20px', marginBottom: '30px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', margin: 0 }}>
                  VENDOR RISK EXECUTIVE BRIEFING
                </h1>
                <p style={{ fontSize: '14px', color: '#64748b', marginTop: '4px' }}>
                  Trust Agent — Automated Due Diligence Platform
                </p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <p style={{ fontSize: '12px', color: '#64748b', margin: 0 }}>Report Date</p>
                <p style={{ fontSize: '14px', fontWeight: 600, color: '#0f172a', margin: 0 }}>
                  {new Date(created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
                </p>
              </div>
            </div>
          </div>

          {/* Vendor + Risk Dial */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
            <div>
              <p style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '2px', marginBottom: '4px' }}>Vendor Under Review</p>
              <h2 style={{ fontSize: '28px', fontWeight: 800, color: '#0f172a', margin: 0 }}>{vendor_name}</h2>
              <p style={{ fontSize: '12px', color: '#64748b', marginTop: '8px' }}>
                Confidence Score: {(risk_assessment.confidence_score * 100).toFixed(0)}%
              </p>
            </div>
            <RiskDial level={risk_assessment.overall_risk_level} confidence={risk_assessment.confidence_score} />
          </div>

          {/* Executive Summary */}
          <div style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '20px', marginBottom: '24px' }}>
            <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '1.5px', color: '#0891b2', marginTop: 0, marginBottom: '10px' }}>Executive Summary</h3>
            <p style={{ fontSize: '14px', lineHeight: '1.7', color: '#334155', margin: 0 }}>
              {risk_assessment.summary}
            </p>
          </div>

          {/* Recommendation */}
          <div style={{ backgroundColor: `${recommendation.color}15`, border: `2px solid ${recommendation.color}`, borderRadius: '8px', padding: '16px', marginBottom: '24px' }}>
            <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '1.5px', color: recommendation.color, marginTop: 0, marginBottom: '8px' }}>Recommendation</h3>
            <p style={{ fontSize: '14px', fontWeight: 600, color: '#0f172a', margin: 0 }}>
              {recommendation.text}
            </p>
          </div>

          {/* Key Findings — two columns */}
          <div style={{ display: 'flex', gap: '20px', marginBottom: '24px' }}>
            {/* OSINT */}
            <div style={{ flex: 1 }}>
              <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '1.5px', color: '#d97706', marginBottom: '10px' }}>External Intelligence (OSINT)</h3>
              {risk_assessment.osint_inferences.length === 0 ? (
                <p style={{ fontSize: '13px', color: '#94a3b8', fontStyle: 'italic' }}>No significant external risks found.</p>
              ) : (
                <ul style={{ paddingLeft: '16px', margin: 0 }}>
                  {risk_assessment.osint_inferences.map((inf, idx) => (
                    <li key={idx} style={{ fontSize: '12px', color: '#334155', lineHeight: '1.6', marginBottom: '6px' }}>{inf}</li>
                  ))}
                </ul>
              )}
            </div>
            {/* RAG */}
            <div style={{ flex: 1 }}>
              <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '1.5px', color: '#6366f1', marginBottom: '10px' }}>Policy Discrepancies (RAG)</h3>
              {risk_assessment.rag_inferences.length === 0 ? (
                <p style={{ fontSize: '13px', color: '#94a3b8', fontStyle: 'italic' }}>No policy discrepancies identified.</p>
              ) : (
                <ul style={{ paddingLeft: '16px', margin: 0 }}>
                  {risk_assessment.rag_inferences.map((inf, idx) => (
                    <li key={idx} style={{ fontSize: '12px', color: '#334155', lineHeight: '1.6', marginBottom: '6px' }}>{inf}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Compliance Gap Status */}
          {totalGaps > 0 && (
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '1.5px', color: '#0891b2', marginBottom: '10px' }}>
                Compliance Gap Resolution Status
              </h3>
              <div style={{ backgroundColor: '#f1f5f9', borderRadius: '8px', padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '13px', color: '#475569' }}>
                  {resolvedGaps} of {totalGaps} gaps resolved ({totalGaps > 0 ? Math.round((resolvedGaps / totalGaps) * 100) : 0}%)
                </span>
                <div style={{ width: '200px', height: '8px', backgroundColor: '#cbd5e1', borderRadius: '4px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${totalGaps > 0 ? (resolvedGaps / totalGaps) * 100 : 0}%`,
                    height: '100%',
                    backgroundColor: resolvedGaps === totalGaps ? '#10b981' : '#0891b2',
                    borderRadius: '4px',
                  }} />
                </div>
              </div>
            </div>
          )}

          {/* Data Gaps */}
          {risk_assessment.data_gaps.length > 0 && (
            <div style={{ marginBottom: '24px' }}>
              <h3 style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '1.5px', color: '#64748b', marginBottom: '10px' }}>Intelligence Gaps</h3>
              <ul style={{ paddingLeft: '16px', margin: 0 }}>
                {risk_assessment.data_gaps.map((gap, idx) => (
                  <li key={idx} style={{ fontSize: '12px', color: '#64748b', lineHeight: '1.6', marginBottom: '4px' }}>{gap}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Footer */}
          <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: '16px', marginTop: '30px', textAlign: 'center' }}>
            <p style={{ fontSize: '10px', color: '#94a3b8', margin: 0 }}>
              Generated by Trust Agent — AI-Powered Vendor Due Diligence Platform • Confidential
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
