import type { CaseDetail, CaseSummary, Metrics, Rule, FeedbackRecord, ReturnRequestPayload, ScoreResponse } from '../types';

const API_URL = import.meta.env.DEV ? "/api" : (import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getMetrics: () => request<Metrics>('/dashboard/metrics'),
  getCases: (query?: string) => request<CaseSummary[]>(`/cases${query ? `?q=${encodeURIComponent(query)}` : ''}`),
  getCase: (id: string) => request<CaseDetail>(`/cases/${id}`),
  getRules: () => request<Rule[]>('/rules'),
  getFeedback: () => request<FeedbackRecord[]>('/feedback'),
  createRule: (payload: Partial<Rule>) =>
    request<Rule>('/rules', { method: 'POST', body: JSON.stringify(payload) }),
  updateRule: (id: string, payload: Partial<Rule>) =>
    request<Rule>(`/rules/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  updateDecision: (id: string, payload: Record<string, unknown>) =>
    request<{ ok: boolean }>(`/cases/${id}/decision`, { method: 'PATCH', body: JSON.stringify(payload) }),
  retrain: () => request<{ ok: boolean; model_version: string }>('/ml/retrain', { method: 'POST' }),
  createReturn: (payload: ReturnRequestPayload) =>
    request<ScoreResponse>('/returns', { method: 'POST', body: JSON.stringify(payload) }),
  scoreReturn: (payload: unknown) =>
    request<ScoreResponse>('/returns/score', { method: 'POST', body: JSON.stringify(payload) }),
};
