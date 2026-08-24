from app.ai import HeuristicResolver
from app.reconciliation import ReconciliationService


def test_demo_batch_reconciles_known_records_and_keeps_exceptions() -> None:
    report = ReconciliationService(resolver=HeuristicResolver()).reconcile_demo()

    assert report.metrics.total_orders == 72
    assert report.metrics.auto_matched == 48
    assert report.metrics.ai_assisted == 12
    assert report.metrics.needs_review == 12
    assert report.metrics.precision == 100.0
    assert report.metrics.recall == 100.0
    assert report.metrics.financial_variance == 0


def test_fee_variance_is_not_force_matched() -> None:
    report = ReconciliationService(resolver=HeuristicResolver()).reconcile_demo()
    result = next(item for item in report.results if item.order_id == "order_0061")

    assert result.status == "needs_review"
    assert result.exception_code == "FEE_VARIANCE"
    assert any(entry.step == "blocked" or entry.step == "resolver" for entry in result.audit)
