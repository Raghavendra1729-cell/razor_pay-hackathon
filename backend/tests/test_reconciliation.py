from app.ai import HeuristicResolver, HuggingFaceResolver
from app.demo_data import demo_batch
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
    assert any(
        entry.step == "blocked" or entry.step == "resolver" for entry in result.audit
    )


class CountingResolver(HeuristicResolver):
    mode = "Test resolver"

    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        self.calls += 1
        return super().resolve(*args, **kwargs)


class OfflineClient:
    def chat_completion(self, **kwargs: object) -> None:
        raise OSError("inference provider unavailable")


def test_no_candidate_records_do_not_spend_model_calls() -> None:
    resolver = CountingResolver()
    ReconciliationService(resolver=resolver).reconcile_demo()

    assert resolver.calls == 12


def test_hugging_face_outage_fails_closed() -> None:
    orders, settlements, _, _ = demo_batch()
    resolver = object.__new__(HuggingFaceResolver)
    resolver.client = OfflineClient()
    resolver.model = "test-model"

    resolution = resolver.resolve(orders[48], [settlements[48]])

    assert resolution.decision == "unresolved"
    assert resolution.selected_settlement_id is None
    assert "left unresolved" in resolution.reason
