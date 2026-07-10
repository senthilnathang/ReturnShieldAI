import type {
  CaseDetail,
  CaseSummary,
  Metrics,
  PaginatedResponse,
  RecordsPage,
  Rule,
  FeedbackRecord,
  ReturnRequestPayload,
  ScoreResponse,
  ReturnEligibility,
  ReturnableOrderItem,
  OrderReturnRecord,
  ReturnAnalysisResponse,
  ReturnDetail,
  OrderImageCompareResponse,
} from '../types';

const API_URL = (import.meta.env.VITE_API_URL ?? "/api");

function recordParams(p: Record<string, unknown>): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(p)) {
    if (v === undefined || v === null || v === '') continue;
    const key = k === 'merchantId' ? 'merchant_id' : k;
    params.set(key, String(v));
  }
  return params.toString();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text().catch(() => 'Unknown error');
    throw new Error(`Request failed with status ${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getMetrics: () => request<Metrics>('/dashboard/metrics'),
  getCases: (skip?: number, limit?: number, query?: string) => {
    const params = new URLSearchParams();
    if (skip) params.set('skip', String(skip));
    if (limit) params.set('limit', String(limit));
    if (query) params.set('q', query);
    const qs = params.toString();
    return request<PaginatedResponse<CaseSummary>>(`/cases${qs ? `?${qs}` : ''}`);
  },
  getCase: (id: string) => request<CaseDetail>(`/cases/${id}`),
  getRules: (skip?: number, limit?: number) => {
    const params = new URLSearchParams();
    if (skip) params.set('skip', String(skip));
    if (limit) params.set('limit', String(limit));
    const qs = params.toString();
    return request<PaginatedResponse<Rule>>(`/rules${qs ? `?${qs}` : ''}`);
  },
  getFeedback: (skip?: number, limit?: number) => {
    const params = new URLSearchParams();
    if (skip) params.set('skip', String(skip));
    if (limit) params.set('limit', String(limit));
    const qs = params.toString();
    return request<PaginatedResponse<FeedbackRecord>>(`/feedback${qs ? `?${qs}` : ''}`);
  },
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
  getImportJobs: (skip?: number, limit?: number) => {
    const params = new URLSearchParams();
    if (skip) params.set('skip', String(skip));
    if (limit) params.set('limit', String(limit));
    const qs = params.toString();
    return request<Array<Record<string, unknown>>>(`/imports${qs ? `?${qs}` : ''}`);
  },

  // Records (orders / payments / returns) — served by the production v1 API (PostgreSQL)
  getOrders: (params: { skip?: number; limit?: number; q?: string; category?: string; merchantId?: string } = {}) => {
    const qs = recordParams(params);
    return request<RecordsPage>(`/v1/orders${qs ? `?${qs}` : ''}`);
  },
  getOrder: (orderId: string) => request<Record<string, unknown>>(`/v1/orders/${orderId}`),
  getOrderStats: (merchantId?: string) =>
    request<Record<string, unknown>>(`/v1/orders/stats${merchantId ? `?merchant_id=${merchantId}` : ''}`),
  getOrderEligibility: (orderId: string) =>
    request<ReturnEligibility>(`/v1/orders/${orderId}/return-eligibility`),
  getOrderReturnableItems: (orderId: string) =>
    request<ReturnableOrderItem[]>(`/v1/orders/${orderId}/returnable-items`),
  getOrderReturns: (orderId: string) =>
    request<{ items: OrderReturnRecord[]; total: number }>(`/v1/orders/${orderId}/returns`),
  createOrderReturn: (orderId: string, payload: Record<string, unknown>, headers?: Record<string, string>) =>
    request<OrderReturnRecord>(`/v1/orders/${orderId}/returns`, {
      method: 'POST',
      body: JSON.stringify(payload),
      headers,
    }),
  compareOrderImage: (orderId: string, payload: { image_data_url: string; filename?: string; mime_type?: string }) =>
    request<OrderImageCompareResponse>(`/v1/orders/${orderId}/return-image-compare`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getReturn: (returnId: string) => request<ReturnDetail>(`/v1/returns/${returnId}`),
  runReturnAnalysis: (returnId: string, payload: { image_data_url: string; filename?: string; mime_type?: string }) =>
    request<ReturnAnalysisResponse>(`/v1/returns/${returnId}/run-analysis`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getPayments: (params: { skip?: number; limit?: number; q?: string; chargeback?: boolean; merchantId?: string } = {}) => {
    const qs = recordParams(params);
    return request<RecordsPage>(`/v1/payments${qs ? `?${qs}` : ''}`);
  },
  getPaymentStats: (merchantId?: string) =>
    request<Record<string, unknown>>(`/v1/payments/stats${merchantId ? `?merchant_id=${merchantId}` : ''}`),
  getReturnsList: (params: { skip?: number; limit?: number; q?: string; status?: string; merchantId?: string } = {}) => {
    const qs = recordParams(params);
    return request<RecordsPage>(`/v1/returns${qs ? `?${qs}` : ''}`);
  },
  getReturnStats: (merchantId?: string) =>
    request<Record<string, unknown>>(`/v1/returns/stats${merchantId ? `?merchant_id=${merchantId}` : ''}`),
  evaluateAlerts: (data: Record<string, unknown>) =>
    request<{ alerts_fired: Array<Record<string, unknown>> }>('/alerts/evaluate', { method: 'POST', body: JSON.stringify(data) }),
  seedModuleData: () =>
    request<{ seeded: boolean; results: Record<string, unknown> }>('/seed', { method: 'POST' }),
  getModuleDashboard: () =>
    request<Record<string, unknown>>('/modules/dashboard'),
  previewKaggle: (datasetId: string, maxPreview?: number) =>
    request<Record<string, unknown>>('/kaggle/preview', { method: 'POST', body: JSON.stringify({ dataset_id: datasetId, max_preview_rows: maxPreview ?? 100 }) }),
  previewKaggleLocal: (path: string, maxPreview?: number) =>
    request<Record<string, unknown>>('/kaggle/preview', { method: 'POST', body: JSON.stringify({ path, max_preview_rows: maxPreview ?? 100 }) }),
  importKaggleWithMapping: (datasetIdOrPath: string, mapping: Record<string, string>, maxRows?: number, isLocal?: boolean) =>
    request<Record<string, unknown>>('/kaggle/import', {
      method: 'POST',
      body: JSON.stringify({
        ...(isLocal ? { path: datasetIdOrPath } : { dataset_id: datasetIdOrPath }),
        mapping,
        max_rows: maxRows ?? 5000,
      }),
    }),
};
