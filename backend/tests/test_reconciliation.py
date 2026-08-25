import json
from types import SimpleNamespace

from app.ai import HeuristicResolver, HuggingFaceResolver, ResolutionCase
from app.demo_data import demo_batch
from app.models import BatchResolutionItem
from app.reconciliation import ReconciliationService


def test_demo_batch_reconciles_known_records_and_keeps_exceptions() -> None:
    report = ReconciliationService(resolver=HeuristicResolver()).reconcile_demo()

    assert report.metrics.total_orders == 72
    assert report.metrics.auto_matched == 48
    assert report.metrics.ai_assisted == 12
    assert report.metrics.needs_review == 12
    assert report.metrics.baseline_match_rate == 66.67
    assert report.metrics.assisted_uplift == 16.66
    assert report.metrics.precision == 100.0
    assert report.metrics.recall == 100.0
    assert report.metrics.financial_variance == 0
    assert report.metrics.model_calls == 0


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

    def resolve_many(self, cases: list[ResolutionCase]):  # type: ignore[no-untyped-def]
        self.calls += 1
        self.case_count = len(cases)
        return super().resolve_many(cases)


class OfflineClient:
    def chat_completion(self, **kwargs: object) -> None:
        raise OSError("inference provider unavailable")


class StaticClient:
    def __init__(self, content: dict[str, object]) -> None:
        self.calls = 0
        self.content = content

    def chat_completion(self, **kwargs: object) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(self.content))
                )
            ]
        )


def test_no_candidate_records_do_not_spend_model_calls() -> None:
    resolver = CountingResolver()
    ReconciliationService(resolver=resolver).reconcile_demo()

    assert resolver.calls == 1
    assert resolver.case_count == 12


def test_hugging_face_outage_fails_closed() -> None:
    orders, settlements, _, _ = demo_batch()
    settlement = next(item for item in settlements if item.settlement_id == "setl_0049")
    resolver = object.__new__(HuggingFaceResolver)
    resolver.client = OfflineClient()
    resolver.model = "test-model"

    run = resolver.resolve_many(
        [ResolutionCase(order=orders[48], candidates=[settlement])]
    )
    resolution = run.resolutions[orders[48].order_id]

    assert resolution.decision == "unresolved"
    assert resolution.selected_settlement_id is None
    assert "left unresolved" in resolution.reason
    assert run.model_calls == 1


def test_hugging_face_output_cannot_cross_order_candidate_boundaries() -> None:
    orders, settlements, _, _ = demo_batch()
    first = next(item for item in settlements if item.settlement_id == "setl_0049")
    second = next(item for item in settlements if item.settlement_id == "setl_0050")
    resolver = object.__new__(HuggingFaceResolver)
    cases = [
        ResolutionCase(order=orders[48], candidates=[first]),
        ResolutionCase(order=orders[49], candidates=[second]),
    ]
    expected = {case.order.order_id: case for case in cases}

    resolutions = resolver._validate_output(
        [
            BatchResolutionItem(
                order_id=orders[48].order_id,
                selected_settlement_id=second.settlement_id,
                decision="match",
                confidence=0.99,
                reason="Wrong candidate from another order.",
            )
        ],
        expected,
    )

    assert all(item.decision == "unresolved" for item in resolutions.values())


def test_duplicate_model_decisions_are_rejected() -> None:
    orders, settlements, _, _ = demo_batch()
    settlement = next(item for item in settlements if item.settlement_id == "setl_0049")
    resolver = object.__new__(HuggingFaceResolver)
    case = ResolutionCase(order=orders[48], candidates=[settlement])
    decision = BatchResolutionItem(
        order_id=case.order.order_id,
        selected_settlement_id=case.candidates[0].settlement_id,
        decision="match",
        confidence=0.8,
        reason="Candidate selected.",
    )

    resolutions = resolver._validate_output(
        [decision, decision], {case.order.order_id: case}
    )

    assert resolutions[case.order.order_id].decision == "unresolved"


def test_hugging_face_resolves_multiple_cases_in_one_request() -> None:
    orders, settlements, _, _ = demo_batch()
    selected = {
        item.settlement_id: item
        for item in settlements
        if item.settlement_id in {"setl_0049", "setl_0050"}
    }
    cases = [
        ResolutionCase(order=orders[48], candidates=[selected["setl_0049"]]),
        ResolutionCase(order=orders[49], candidates=[selected["setl_0050"]]),
    ]
    client = StaticClient(
        {
            "resolutions": [
                {
                    "order_id": case.order.order_id,
                    "selected_settlement_id": case.candidates[0].settlement_id,
                    "decision": "match",
                    "confidence": 0.91,
                    "reason": "Noisy reference identifier agrees.",
                }
                for case in cases
            ]
        }
    )
    resolver = object.__new__(HuggingFaceResolver)
    resolver.client = client
    resolver.model = "test-model"

    run = resolver.resolve_many(cases)

    assert client.calls == 1
    assert run.model_calls == 1
    assert all(item.decision == "match" for item in run.resolutions.values())
