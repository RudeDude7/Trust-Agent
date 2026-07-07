import type { AnalysisResponse, SavedAudit, ChatResponse, GapAction, RiskAssessment } from './types';
import { supabase } from './supabase';
const rawApiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE = rawApiUrl.replace(/\/$/, '');
async function getAuthHeaders() {
  const { data } = await supabase.auth.getSession();
  if (!data.session) throw new Error('Not authenticated');
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${data.session.access_token}`
  };
}

export const uploadPolicy = async (file: File, role: 'internal' | 'vendor'): Promise<void> => {
  const headers = await getAuthHeaders();
  // Remove Content-Type so the browser can automatically set it with the boundary for FormData
  const { 'Content-Type': _, ...headersWithoutContentType } = headers;
  
  const formData = new FormData();
  formData.append('file', file);
  formData.append('role', role);

  const res = await fetch(`${API_BASE}/upload_policy`, {
    method: 'POST',
    headers: headersWithoutContentType,
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || `Upload failed with status ${res.status}`);
  }
};

export const runAnalysis = async (
  vendorName: string, 
  vendorUrl?: string,
  onProgress?: (msg: string) => void
): Promise<AnalysisResponse> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ vendor_name: vendorName, vendor_url: vendorUrl }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || `Analysis failed with status ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No readable stream received from server.");

  const decoder = new TextDecoder();
  let buffer = '';
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    
    // The last element might be an incomplete JSON string if the chunk was split mid-line
    buffer = lines.pop() || '';
    
    for (const line of lines) {
      if (!line.trim()) continue;
      
      try {
        const data = JSON.parse(line);
        if (data.type === 'progress' && onProgress) {
          onProgress(data.message);
        } else if (data.type === 'complete') {
          return data as AnalysisResponse;
        } else if (data.type === 'error') {
          throw new Error(data.message);
        }
      } catch (err: any) {
        // If it's a parsing error we ignore and wait for next chunk,
        // but since we split by \n and backend writes \n at end of JSON, 
        // it should always be valid unless it's a thrown Error from backend.
        if (err.message !== "Unexpected end of JSON input") {
          throw err;
        }
      }
    }
  }

  // Process any remaining buffer after stream closes
  if (buffer.trim()) {
    try {
      const data = JSON.parse(buffer);
      if (data.type === 'progress' && onProgress) {
        onProgress(data.message);
      } else if (data.type === 'complete') {
        return data as AnalysisResponse;
      } else if (data.type === 'error') {
        throw new Error(data.message);
      }
    } catch (err: any) {
      // Ignore final parse error if it's broken
    }
  }

  throw new Error("Analysis stream ended without returning a final result.");
};

export const sendChatMessage = async (
  sessionId: string,
  message: string
): Promise<ChatResponse> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ session_id: sessionId, message }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || `API error: ${res.status}`);
  }
  
  return res.json();
};

export const generateRemediation = async (sessionId: string): Promise<string> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/generate_remediation`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ session_id: sessionId })
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to generate remediation draft');
  return data.draft;
};

export const fetchAudits = async (): Promise<SavedAudit[]> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/audits`, {
    headers,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || `API error: ${res.status}`);
  }
  
  const data = await res.json();
  return data.audits || [];
};

export const deleteAudit = async (sessionId: string): Promise<void> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/audits/${sessionId}`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) throw new Error('Failed to delete audit');
};

export const updateGapStatus = async (
  sessionId: string,
  gapIndex: number,
  category: 'osint' | 'rag' | 'data_gap',
  status: 'open' | 'accepted' | 'remediation' | 'exemption',
  note: string = '',
  assignedTo: string | null = null
): Promise<GapAction[]> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/update_gap_status`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ session_id: sessionId, gap_index: gapIndex, category, status, note, assigned_to: assignedTo }),
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to update gap status');
  return data.gap_actions;
};

export const fetchGapActions = async (sessionId: string): Promise<GapAction[]> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/gap_actions/${sessionId}`, {
    headers,
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to fetch gap actions');
  return data.gap_actions;
};

export const evaluateSandbox = async (
  sessionId: string,
  disabledClauses: string[]
): Promise<RiskAssessment> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/sandbox_evaluate`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ session_id: sessionId, disabled_clauses: disabledClauses }),
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to run policy sandbox evaluation');
  return data.simulated_risk;
};

export const watchVendor = async (vendorName: string): Promise<void> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/watch_vendor`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ vendor_name: vendorName }),
  });
  if (!res.ok) throw new Error('Failed to watch vendor');
};

export const unwatchVendor = async (vendorName: string): Promise<void> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/watch_vendor/${encodeURIComponent(vendorName)}`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) throw new Error('Failed to unwatch vendor');
};

export const fetchWatchedVendors = async (): Promise<any[]> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/watched_vendors`, { headers });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to fetch watched vendors');
  return data.watched_vendors;
};

export const fetchThreatAlerts = async (): Promise<any[]> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/threat_alerts`, { headers });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to fetch threat alerts');
  return data.alerts;
};

export const markAlertRead = async (alertId: string): Promise<void> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/threat_alerts/${alertId}/read`, {
    method: 'POST',
    headers,
  });
  if (!res.ok) throw new Error('Failed to mark alert as read');
};

export const fetchEmployees = async (): Promise<any[]> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/employees`, { headers });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to fetch employees');
  return data.employees;
};

export const addEmployee = async (name: string, position: string): Promise<any> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/employees`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ name, position }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Failed to add employee');
  return data;
};

export const deleteEmployee = async (employeeId: string): Promise<void> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/employees/${employeeId}`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) throw new Error('Failed to delete employee');
};
