import React, { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink, FileText } from 'lucide-react';
import type { OSINTFinding } from '../types';

interface SourceEvidenceProps {
    osintFindings?: OSINTFinding[];
    ragClauses?: { clause_text: string; parent_context: string; role: string; source: string }[];
    variant: 'osint' | 'rag';
}

const TYPE_COLORS: Record<string, string> = {
    breach_report: "bg-red-100 text-red-600",
    regulatory_filing: "bg-orange-100 text-orange-600",
    legal_action: "bg-amber-100 text-amber-700",
    privacy_concern: "bg-purple-100 text-purple-600",
    financial_instability: "bg-rose-100 text-rose-600",
    operational_outage: "bg-yellow-100 text-yellow-700",
    esg_unethical_practices: "bg-pink-100 text-pink-600",
    state_sponsored_ties: "bg-red-100 text-red-700",
    news_article: "bg-stone-100 text-stone-500",
};

function OsintSection({ findings }: { findings: OSINTFinding[] }) {
    const [isExpanded, setIsExpanded] = useState(false);
    const filtered = findings.filter(f => f.relevance_score > 0.2).sort((a, b) => b.relevance_score - a.relevance_score);

    return (
        <div className="mt-4 border-t border-stone-200 pt-4">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-2 text-xs font-semibold text-stone-400 hover:text-stone-600 uppercase tracking-widest transition-colors"
            >
                <ExternalLink size={14} />
                {findings.length} Source{findings.length !== 1 ? 's' : ''} Referenced
                {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            {isExpanded && (
                <div className="mt-3 space-y-2">
                    {filtered.map((finding, idx) => {
                        const badgeColor = TYPE_COLORS[finding.finding_type] || "bg-stone-100 text-stone-500";
                        return (
                            <a
                                key={idx}
                                href={finding.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-start gap-3 p-3 rounded-lg bg-white border border-stone-200 hover:border-orange-300 hover:shadow-sm transition-all group"
                            >
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${badgeColor}`}>
                                            {finding.finding_type.replace(/_/g, ' ')}
                                        </span>
                                        <span className="text-[10px] text-stone-400 font-medium">
                                            relevance: {(finding.relevance_score * 100).toFixed(0)}%
                                        </span>
                                    </div>
                                    <p className="text-sm font-medium text-stone-700 group-hover:text-orange-700 transition-colors truncate">
                                        {finding.title}
                                    </p>
                                    <p className="text-xs text-stone-400 truncate mt-0.5">
                                        {finding.source_url}
                                    </p>
                                </div>
                                <ExternalLink size={14} className="text-stone-300 group-hover:text-orange-400 mt-1 shrink-0" />
                            </a>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

function RagSection({ clauses }: { clauses: { clause_text: string; parent_context: string; role: string; source: string }[] }) {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
        <div className="mt-4 border-t border-stone-200 pt-4">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-2 text-xs font-semibold text-stone-400 hover:text-stone-600 uppercase tracking-widest transition-colors"
            >
                <FileText size={14} />
                {clauses.length} Policy Clause{clauses.length !== 1 ? 's' : ''} Referenced
                {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            {isExpanded && (
                <div className="mt-3 space-y-2">
                    {clauses.map((clause, idx) => {
                        const fileName = clause.source.split('/').pop() || clause.source;
                        return (
                            <div
                                key={idx}
                                className="p-3 rounded-lg bg-white border border-stone-200"
                            >
                                <div className="flex items-center gap-2 mb-2">
                                    <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${clause.role === 'internal' ? "bg-blue-100 text-blue-600" : "bg-amber-100 text-amber-600"}`}>
                                        {clause.role}
                                    </span>
                                    <span className="text-[10px] text-stone-400 font-medium truncate">
                                        {fileName}
                                    </span>
                                </div>
                                <p className="text-xs text-stone-600 leading-relaxed line-clamp-3">
                                    {clause.clause_text}
                                </p>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

export const SourceEvidence: React.FC<SourceEvidenceProps> = ({ osintFindings, ragClauses, variant }) => {
    if (variant === 'osint') {
        if (!osintFindings || osintFindings.length === 0) return null;
        return <OsintSection findings={osintFindings} />;
    }

    if (!ragClauses || ragClauses.length === 0) return null;
    const relevantClauses = ragClauses.filter(c => c.role === variant || variant === 'rag');
    if (relevantClauses.length === 0) return null;
    return <RagSection clauses={relevantClauses} />;
};