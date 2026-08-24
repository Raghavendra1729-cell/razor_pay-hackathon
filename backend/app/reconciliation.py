from __future__ import annotations

from .ai import Resolver, configured_resolver
from .demo_data import demo_batch
from .models import (
    AuditEntry,
    BankDeposit,
    MerchantOrder,
    ReconciliationReport,
    ReconciliationResult,
    ReportMetrics,
    ResultStatus,
    Settlement,
)


class ReconciliationService:
    def __init__(self, resolver: Resolver | None = None) -> None:
        self.resolver = resolver or configured_resolver()

    def reconcile_demo(self) -> ReconciliationReport:
        orders, settlements, deposits, ground_truth = demo_batch()
        results: list[ReconciliationResult] = []
        used_settlements: set[str] = set()
        used_deposits: set[str] = set()

        for order in orders:
            result = self._reconcile_order(
                order, settlements, deposits, used_settlements, used_deposits
            )
            results.append(result)
            if result.settlement_id:
                used_settlements.add(result.settlement_id)
            if result.bank_txn_id:
                used_deposits.add(result.bank_txn_id)

        matched = [item for item in results if item.status != "needs_review"]
        correct = sum(
            1
            for item in matched
            if item.order_id in ground_truth
            and ground_truth[item.order_id] == (item.settlement_id, item.bank_txn_id)
        )
        true_matchable = len(ground_truth)
        metrics = ReportMetrics(
            total_orders=len(orders),
            auto_matched=sum(item.status == "auto_matched" for item in results),
            ai_assisted=sum(item.status == "ai_assisted" for item in results),
            needs_review=sum(item.status == "needs_review" for item in results),
            match_rate=self._percentage(len(matched), len(results)),
            precision=self._percentage(correct, len(matched)),
            recall=self._percentage(correct, true_matchable),
            unresolved_value=sum(
                item.gross_amount for item in results if item.status == "needs_review"
            ),
            financial_variance=self._financial_variance(results, settlements, deposits),
            model_mode=self.resolver.mode,
        )
        return ReconciliationReport(metrics=metrics, results=results)

    def _reconcile_order(
        self,
        order: MerchantOrder,
        settlements: list[Settlement],
        deposits: list[BankDeposit],
        used_settlements: set[str],
        used_deposits: set[str],
    ) -> ReconciliationResult:
        audit = [
            AuditEntry(
                step="normalised",
                detail="Amounts are evaluated in paise; dates are ISO-normalised.",
            )
        ]
        direct = [
            item
            for item in settlements
            if item.settlement_id not in used_settlements
            and item.reference == order.payment_id
        ]
        if len(direct) == 1:
            verified = self._verified_pair(direct[0], deposits, used_deposits)
            if verified:
                audit.extend(
                    [
                        AuditEntry(
                            step="exact_match",
                            detail=f"Payment reference matched {direct[0].settlement_id}.",
                        ),
                        AuditEntry(
                            step="verified",
                            detail="Gross amount, fees, tax and bank net amount balanced.",
                        ),
                    ]
                )
                return self._matched(
                    order,
                    direct[0],
                    verified,
                    "auto_matched",
                    1.0,
                    "Exact reference and financial invariant matched.",
                    audit,
                )
            audit.append(
                AuditEntry(
                    step="blocked",
                    detail="The direct reference exists but its fee or net amount cannot be independently verified.",
                )
            )
            return self._unresolved(
                order,
                audit,
                "FEE_VARIANCE",
                "The payment reference was found, but the settlement does not satisfy the fee and net-amount checks.",
            )

        candidates = [
            item
            for item in settlements
            if item.settlement_id not in used_settlements
            and item.gross_amount == order.gross_amount
            and abs((item.settled_at - order.created_at).days) <= 3
        ]
        audit.append(
            AuditEntry(
                step="candidate_search",
                detail=f"Found {len(candidates)} constrained candidate(s).",
            )
        )
        if not candidates:
            return self._unresolved(
                order,
                audit,
                self._exception_code(order, settlements, deposits),
                "No settlement fell within the constrained amount and date window.",
            )

        resolution = self.resolver.resolve(order, candidates)
        audit.append(AuditEntry(step="resolver", detail=resolution.reason))

        settlement = next(
            (
                item
                for item in candidates
                if item.settlement_id == resolution.selected_settlement_id
            ),
            None,
        )
        if resolution.decision == "match" and settlement:
            verified = self._verified_pair(settlement, deposits, used_deposits)
            if verified:
                audit.append(
                    AuditEntry(
                        step="verified",
                        detail="Constrained resolution passed the financial invariant and bank-evidence check.",
                    )
                )
                return self._matched(
                    order,
                    settlement,
                    verified,
                    "ai_assisted",
                    resolution.confidence,
                    resolution.reason,
                    audit,
                )
            audit.append(
                AuditEntry(
                    step="blocked",
                    detail="A proposed match failed independent financial verification.",
                )
            )
            return self._unresolved(
                order,
                audit,
                "VERIFICATION_FAILED",
                "The candidate did not balance against a unique bank deposit.",
            )

        exception_code = self._exception_code(order, settlements, deposits)
        return self._unresolved(order, audit, exception_code, resolution.reason)

    @staticmethod
    def _verified_pair(
        settlement: Settlement, deposits: list[BankDeposit], used_deposits: set[str]
    ) -> BankDeposit | None:
        expected_net = settlement.gross_amount - settlement.fee - settlement.tax
        if expected_net != settlement.net_amount or settlement.fee <= 0:
            return None
        candidates = [
            item
            for item in deposits
            if item.bank_txn_id not in used_deposits
            and item.amount == settlement.net_amount
            and settlement.settlement_id.upper() in item.narration.upper()
        ]
        return candidates[0] if len(candidates) == 1 else None

    @staticmethod
    def _matched(
        order: MerchantOrder,
        settlement: Settlement,
        deposit: BankDeposit,
        status: ResultStatus,
        confidence: float,
        explanation: str,
        audit: list[AuditEntry],
    ) -> ReconciliationResult:
        return ReconciliationResult(
            order_id=order.order_id,
            payment_id=order.payment_id,
            gross_amount=order.gross_amount,
            status=status,
            settlement_id=settlement.settlement_id,
            bank_txn_id=deposit.bank_txn_id,
            confidence=confidence,
            explanation=explanation,
            audit=audit,
        )

    @staticmethod
    def _unresolved(
        order: MerchantOrder, audit: list[AuditEntry], code: str, explanation: str
    ) -> ReconciliationResult:
        return ReconciliationResult(
            order_id=order.order_id,
            payment_id=order.payment_id,
            gross_amount=order.gross_amount,
            status="needs_review",
            confidence=0.0,
            explanation=explanation,
            exception_code=code,
            audit=audit,
        )

    @staticmethod
    def _exception_code(
        order: MerchantOrder, settlements: list[Settlement], deposits: list[BankDeposit]
    ) -> str:
        if any(item.reference == order.payment_id for item in settlements):
            return "FEE_VARIANCE"
        same_amount = [item for item in deposits if item.amount == order.gross_amount]
        if len(same_amount) > 1:
            return "DUPLICATE_DEPOSIT"
        return "MISSING_SETTLEMENT"

    @staticmethod
    def _percentage(numerator: int, denominator: int) -> float:
        return round((numerator / denominator * 100) if denominator else 0, 2)

    @staticmethod
    def _financial_variance(
        results: list[ReconciliationResult],
        settlements: list[Settlement],
        deposits: list[BankDeposit],
    ) -> int:
        settlement_by_id = {item.settlement_id: item for item in settlements}
        deposit_by_id = {item.bank_txn_id: item for item in deposits}
        variance = 0
        for result in results:
            if not result.settlement_id or not result.bank_txn_id:
                continue
            settlement = settlement_by_id[result.settlement_id]
            deposit = deposit_by_id[result.bank_txn_id]
            expected_net = settlement.gross_amount - settlement.fee - settlement.tax
            variance += abs(expected_net - settlement.net_amount) + abs(
                settlement.net_amount - deposit.amount
            )
        return variance
