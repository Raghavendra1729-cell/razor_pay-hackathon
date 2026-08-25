from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class MerchantOrder(BaseModel):
    order_id: str
    payment_id: str
    customer_label: str
    gross_amount: int = Field(description="Amount in paise")
    created_at: date


class Settlement(BaseModel):
    settlement_id: str
    reference: str
    gross_amount: int
    fee: int
    tax: int
    net_amount: int
    settled_at: date


class BankDeposit(BaseModel):
    bank_txn_id: str
    narration: str
    amount: int
    posted_at: date


class Resolution(BaseModel):
    selected_settlement_id: str | None
    decision: Literal["match", "unresolved"]
    confidence: float = Field(ge=0, le=1)
    reason: str


class BatchResolutionItem(Resolution):
    order_id: str


class BatchResolution(BaseModel):
    resolutions: list[BatchResolutionItem]


class AuditEntry(BaseModel):
    step: str
    detail: str


ResultStatus = Literal["auto_matched", "ai_assisted", "needs_review"]


class ReconciliationResult(BaseModel):
    order_id: str
    payment_id: str
    gross_amount: int
    status: ResultStatus
    settlement_id: str | None = None
    bank_txn_id: str | None = None
    confidence: float
    explanation: str
    exception_code: str | None = None
    audit: list[AuditEntry]


class ReportMetrics(BaseModel):
    total_orders: int
    auto_matched: int
    ai_assisted: int
    needs_review: int
    match_rate: float
    baseline_match_rate: float
    assisted_uplift: float
    precision: float
    recall: float
    unresolved_value: int
    financial_variance: int
    model_mode: str
    model_calls: int
    resolver_latency_ms: int


class ReconciliationReport(BaseModel):
    metrics: ReportMetrics
    results: list[ReconciliationResult]
