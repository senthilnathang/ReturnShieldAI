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

export type ReturnEligibility = {
  eligible: boolean;
  return_window_days: number;
  return_window_expires_at?: string | null;
  reason?: string | null;
  message?: string | null;
  returnable_item_count: number;
  can_override: boolean;
};

export type ReturnableOrderItem = {
  order_item_id: string;
  order_id: string;
  sku?: string | null;
  product_name?: string | null;
  category?: string | null;
  ordered_quantity: number;
  previously_returned_quantity: number;
  available_return_quantity: number;
  return_quantity: number;
  product_value?: number | null;
  serial_number?: string | null;
  imei?: string | null;
  requires_serial: boolean;
};

export type ReturnItemRecord = {
  id: string;
  return_id: string;
  order_id: string;
  sku?: string | null;
  product_name?: string | null;
  category?: string | null;
  quantity: number;
  product_value?: number | null;
  declared_condition?: string | null;
  warehouse_condition?: string | null;
  serial_number_hash?: string | null;
  imei_hash?: string | null;
  item_match_status?: string | null;
  created_at: string;
};

export type OrderReturnRecord = {
  id: string;
  external_return_id?: string | null;
  order_id: string;
  merchant_id: string;
  customer_id: string;
  created_by?: string | null;
  return_reason_category?: string | null;
  return_reason?: string | null;
  detailed_description?: string | null;
  condition_reported?: string | null;
  return_method?: string | null;
  pickup_address_id?: string | null;
  preferred_refund_method?: string | null;
  return_status?: string | null;
  fraud_screening_status?: string | null;
  eligibility_override?: boolean;
  eligibility_override_reason?: string | null;
  return_date?: string | null;
  hours_after_delivery?: number | null;
  created_at: string;
  updated_at: string;
  fraud_risk_score?: number | null;
  fraud_decision?: string | null;
  refund_amount?: number | null;
  item_count?: number;
  items?: ReturnItemRecord[];
  return_eligibility?: ReturnEligibility;
  return_count?: number;
  latest_return?: OrderReturnRecord | null;
};

export type ReturnDetail = OrderReturnRecord & {
  order: Record<string, unknown>;
  customer: Record<string, unknown>;
  eligibility?: ReturnEligibility | null;
  timeline: Array<{ label: string; time: string }>;
};
export type FraudScoreRecord = {
  id: string;
  merchant_id: string;
  return_id: string;
  customer_id: string;
  rule_score: number;
  structured_ml_score: number;
  nlp_score: number;
  graph_score: number;
  anomaly_score: number;
  final_score: number;
  risk_level?: RiskLevel | null;
  decision?: Decision | null;
  reason_codes_json?: unknown;
  score_breakdown_json?: Record<string, unknown> | null;
  created_at: string;
};

export type FraudCaseRecord = {
  id: string;
  merchant_id: string;
  return_id: string;
  customer_id: string;
  fraud_score_id?: string | null;
  case_status?: string | null;
  priority?: string | null;
  assigned_to?: string | null;
  recommended_action?: string | null;
  case_summary?: string | null;
  created_at: string;
  updated_at: string;
  closed_at?: string | null;
};

export type ReturnAnalysisScoreResult = {
  rule_score: number;
  structured_ml_score: number;
  nlp_score: number;
  graph_score: number;
  anomaly_score: number;
  final_score: number;
  risk_level: RiskLevel;
  decision: Decision;
  reason_codes: string[];
  score_breakdown: Record<string, unknown>;
};

export type ReturnAnalysisResponse = {
  return_detail: ReturnDetail;
  image_review?: OrderImageCompareResponse | null;
  score?: FraudScoreRecord | null;
  fraud_case?: FraudCaseRecord | null;
  score_result: ReturnAnalysisScoreResult;
  explanation: string;
  recommended_action: string;
  explainability: ExplainabilityPanel;
  reason_codes: string[];
  score_breakdown: Record<string, unknown>;
  decision_trace: Array<{ stage: string; value: string | number }>;
  model_version?: string | null;
};


export type OrderImageCompareResponse = {
  order_id: string;
  matched: boolean;
  confidence: number;
  ocr_text: string;
  detected_product_name?: string | null;
  detected_sku?: string | null;
  detected_serial_number?: string | null;
  detected_imei?: string | null;
  mismatch_reasons: string[];
  evidence: string[];
  summary: string;
  provider_model?: string | null;
};
