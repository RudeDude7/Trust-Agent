export interface RiskAssessment {
  overall_risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  confidence_score: number;
  summary: string;
  osint_inferences: string[];
  rag_inferences: string[];
  comparative_analysis: string;
  data_gaps: string[];
}

export interface AnalysisResponse {
  status: string;
  vendor: string;
  session_id: string;
  risk_assessment: RiskAssessment;
}

export interface ChatResponse {
  status: string;
  response: string;
}

export interface SavedAudit {
  vendor: string;
  timestamp: string;
  session_id: string;
  data: RiskAssessment;
}
