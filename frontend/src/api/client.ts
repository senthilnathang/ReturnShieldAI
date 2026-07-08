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

  // New module API endpoints
  searchEmbeddings: (text: string, k?: number) =>
    request<{ results: Array<{ score: number; metadata: Record<string, unknown> }> }>('/embeddings/search', { method: 'POST', body: JSON.stringify({ text, k }) }),
  indexEmbeddings: () =>
    request<{ indexed: number }>('/embeddings/index', { method: 'POST' }),
  getEmbeddingStats: () =>
    request<{ size: number; active_model: string }>('/embeddings/stats'),
  getGraphSummary: () =>
    request<Record<string, unknown>>('/graph/summary'),
  getCaseGraph: (id: string) =>
    request<Record<string, unknown>>(`/graph/case/${id}`),
  getCaseTimeline: (id: string) =>
    request<{ events: Array<{ label: string; time: string; type: string; detail: string }> }>(`/timeline/${id}`),
  getInvestigationReport: (id: string) =>
    request<Record<string, unknown>>(`/investigation/${id}`),
  getPatterns: () =>
    request<{ patterns: Array<Record<string, unknown>>; total: number }>('/patterns'),
  matchPatterns: (data: Record<string, unknown>) =>
    request<{ matches: Array<Record<string, unknown>> }>('/patterns/match', { method: 'POST', body: JSON.stringify(data) }),
  getMerchants: () =>
    request<{ merchants: string[] }>('/merchants'),
  getMerchantConfig: (id: string) =>
    request<Record<string, unknown>>(`/merchants/${id}`),
  getModels: () =>
    request<Record<string, unknown>>('/models'),
  getMonitoringPerformance: () =>
    request<Record<string, unknown>>('/monitoring/performance'),
  evaluateAlerts: (data: Record<string, unknown>) =>
    request<{ alerts_fired: Array<Record<string, unknown>> }>('/alerts/evaluate', { method: 'POST', body: JSON.stringify(data) }),
};
