import type { AnalysisResponse, SavedAudit, ChatResponse, GapAction } from './types';
import { supabase } from './supabase';

const API_BASE = 'https://rudedude7-trust-agent.hf.space';

// Helper to get auth headers
async function getAuthHeaders() {
  const { data } = await supabase.auth.getSession();
  if (!data.session) throw new Error('Not authenticated');
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${data.session.access_token}`
  };
}

export const uploadPolicy = async (file: File, role: 'internal' | 'vendor'): Promise<void> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('role', role);

  const res = await fetch(`${API_BASE}/upload_policy`, {
    method: 'POST',
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

export const updateGapStatus = async (
  sessionId: string,
  gapIndex: number,
  category: 'osint' | 'rag' | 'data_gap',
  status: 'open' | 'accepted' | 'remediation' | 'exemption',
  note: string = ''
): Promise<GapAction[]> => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/update_gap_status`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ session_id: sessionId, gap_index: gapIndex, category, status, note }),
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
