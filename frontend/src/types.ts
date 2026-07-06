export interface Employee {
  id: string;
  name: string;
  position: string;
  created_at?: string;
}

export interface GapAction {
  gap_index: number;
  category: 'osint' | 'rag' | 'data_gap';
  status: 'open' | 'accepted' | 'remediation' | 'exemption';
  note: string;
  assigned_to?: string | null;
  updated_at: string;
}

export interface RiskAssessment {
  overall_risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  confidence_score: number;
  summary: string;
  osint_inferences: string[];
  rag_inferences: string[];
  comparative_analysis: string;
  data_gaps: string[];
  gap_actions?: GapAction[];
  raw_rag_clauses?: { clause_text: string; parent_context: string; role: string; source: string }[];
  raw_osint_findings?: string[];
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
  vendor_name: string;
  created_at: string;
  session_id: string;
  risk_assessment: RiskAssessment;
  chat_history: { role: 'user' | 'agent', content: string }[];
}

export interface WatchedVendor {
  vendor_name: string;
  created_at: string;
}

export interface ThreatAlert {
  id: string;
  user_id: string;
  vendor_name: string;
  alert_title: string;
  alert_summary: string;
  source_url: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  is_read: boolean;
  created_at: string;
}

