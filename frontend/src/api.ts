import type { AnalysisResponse, ChatResponse } from './types';

const API_BASE = 'https://rudedude7-trust-agent.hf.space';

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

export const analyzeVendor = async (vendorName: string, vendorUrl?: string): Promise<AnalysisResponse> => {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vendor_name: vendorName, vendor_url: vendorUrl }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || `Analysis failed with status ${res.status}`);
  }

  return res.json();
};

export const sendChatMessage = async (
  vendorName: string,
  context: string,
  history: { role: string; content: string }[],
  message: string
): Promise<ChatResponse> => {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vendor_name: vendorName, context, history, message }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || `API error: ${res.status}`);
  }
  
  return res.json();
};
