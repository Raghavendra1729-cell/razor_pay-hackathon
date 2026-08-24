export type AuditEntry = {
  step: string;
  detail: string;
};

export type ResultStatus = "auto_matched" | "ai_assisted" | "needs_review";

export type ReconciliationResult = {
  order_id: string;
  payment_id: string;
  gross_amount: number;
  status: ResultStatus;
  settlement_id: string | null;
  bank_txn_id: string | null;
  confidence: number;
  explanation: string;
  exception_code: string | null;
  audit: AuditEntry[];
};

export type Report = {
  metrics: {
    total_orders: number;
    auto_matched: number;
    ai_assisted: number;
    needs_review: number;
    match_rate: number;
    precision: number;
    recall: number;
    unresolved_value: number;
    financial_variance: number;
    model_mode: string;
  };
  results: ReconciliationResult[];
};
