export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH';
export type Decision = 'AUTO_APPROVE' | 'MANUAL_REVIEW' | 'HOLD_REFUND_HIGH_RISK';

export type ScoreBreakdown = {
  rule_score: number;
  structured_ml_score: number;
  nlp_score: number;
  anomaly_score: number;
};

export type ReturnRequestPayload = {
  customer: {
    name: string;
    email: string;
    phone?: string;
    account_age_days?: number;
    address?: string;
    device_id?: string;
    lifetime_orders?: number;
    lifetime_returns?: number;
  };
  order: {
    sku: string;
    product_name: string;
    category: string;
    product_value: number;
    expected_weight: number;
    payment_method?: string;
    payment_method_risk_score?: number;
    delivery_date: string;
    delivery_status?: string;
  };
  return_data: {
    return_reason: string;
    chat_transcript?: string;
    email_text?: string;
    returned_weight?: number;
    condition_reported?: string;
    delivery_photo_url?: string;
    return_photo_url?: string;
    shipping_label_text?: string;
    ocr_text?: string;
  };
};

export type ExplainabilitySignal = {
  label: string;
  score: number;
  weight: number;
  impact: number;
  tone: string;
  detail: string;
};

export type ExplainabilityDriver = {
  label: string;
  impact: number;
  detail: string;
};

export type ExplainabilityPanel = {
  signal_contributions: ExplainabilitySignal[];
  top_positive_drivers: ExplainabilityDriver[];
  top_negative_drivers: ExplainabilityDriver[];
  why_flagged_summary: string;
};

export type ScoreResponse = {
  return_id: string;
  case_id: string;
  customer_risk_score: number;
  risk_score: number;
  risk_level: RiskLevel;
  decision: Decision;
  recommended_action: string;
  score_breakdown: ScoreBreakdown;
  reason_codes: string[];
  explanation: string;
  decision_trace: Array<{ stage: string; value: string | number }>;
  explainability: ExplainabilityPanel;
  advanced_signals: Record<string, unknown>;
  model_version?: string | null;
};

export type CaseSummary = {
  id: string;
  return_id: string;
  customer_name: string;
  product_name: string;
  return_reason: string;
  customer_risk_score: number;
  risk_score: number;
  risk_level: RiskLevel;
  decision: Decision;
  status: string;
  created_at: string;
};

export type CaseDetail = CaseSummary & {
  customer: {
    name: string;
    email: string;
    phone: string;
    account_age_days: number;
    address: string;
    device_id: string;
    lifetime_orders: number;
    lifetime_returns: number;
  };
  order: {
    sku: string;
    product_name: string;
    category: string;
    product_value: number;
    expected_weight: number;
    payment_method: string;
    payment_method_risk_score: number;
    delivery_date: string;
    delivery_status: string;
  };
  return_data: {
    return_reason: string;
    chat_transcript: string;
    email_text: string;
    returned_weight: number;
    condition_reported: string;
  };
  return?: {
    return_reason: string;
    chat_transcript: string;
    email_text: string;
    returned_weight: number;
    condition_reported: string;
  };
  score_breakdown: ScoreBreakdown;
  reason_codes: string[];
  explanation: string;
  recommended_action: string;
  decision_trace: Array<{ stage: string; value: string | number }>;
  explainability: ExplainabilityPanel;
  advanced_signals: Record<string, unknown>;
  timeline: Array<{ label: string; time: string }>;
};

export type Rule = {
  id: string;
  name: string;
  description: string;
  condition: string;
  score: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type Metrics = {
  totals: Record<string, number>;
  charts: Record<string, Array<{ label: string; value: number }>>;
  model: Record<string, string | number | null>;
};


export type PaginatedResponse<T> = {
  items: T[];
  total: number;
};


export type RecordsPage = {
  items: Array<Record<string, unknown>>;
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type FeedbackRecord = {
  id: string;
  case_id: string;
  analyst_decision: string;
  confirmed_label: string;
  notes: string;
  created_at: string;
  customer_name: string;
  product_name: string;
  risk_score: number;
  risk_level: RiskLevel;
};
