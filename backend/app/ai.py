from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from huggingface_hub.utils import HfHubHTTPError
from pydantic import ValidationError
from requests import RequestException

from .models import (
    BatchResolution,
    BatchResolutionItem,
    MerchantOrder,
    Resolution,
    Settlement,
)


@dataclass(frozen=True)
class ResolutionCase:
    order: MerchantOrder
    candidates: list[Settlement]


@dataclass(frozen=True)
class ResolverRun:
    resolutions: dict[str, Resolution]
    model_calls: int
    latency_ms: int


class Resolver(Protocol):
    mode: str

    def resolve_many(self, cases: list[ResolutionCase]) -> ResolverRun: ...


class HeuristicResolver:
    """Safe local fallback: it only picks a single already-constrained candidate."""

    mode = "Deterministic fallback (HF token not configured)"

    @staticmethod
    def _resolve(order: MerchantOrder, candidates: list[Settlement]) -> Resolution:
        order_numbers = {int(value) for value in re.findall(r"\d+", order.payment_id)}
        reference_matches = [
            candidate
            for candidate in candidates
            if order_numbers.intersection(
                int(value) for value in re.findall(r"\d+", candidate.reference)
            )
        ]
        if len(reference_matches) == 1:
            candidate = reference_matches[0]
            return Resolution(
                selected_settlement_id=candidate.settlement_id,
                decision="match",
                confidence=0.74,
                reason="One constrained settlement contains the normalised payment identifier.",
            )
        return Resolution(
            selected_settlement_id=None,
            decision="unresolved",
            confidence=0.0,
            reason="No unique, verifiable settlement candidate is available.",
        )

    def resolve_many(self, cases: list[ResolutionCase]) -> ResolverRun:
        started = perf_counter()
        resolutions = {
            case.order.order_id: self._resolve(case.order, case.candidates)
            for case in cases
        }
        return ResolverRun(
            resolutions=resolutions,
            model_calls=0,
            latency_ms=round((perf_counter() - started) * 1000),
        )


class HuggingFaceResolver:
    mode = "Hugging Face structured output"

    def __init__(self, token: str, model: str, provider: str, timeout: float) -> None:
        from huggingface_hub import InferenceClient

        self.client = InferenceClient(api_key=token, provider=provider, timeout=timeout)
        self.model = model

    @staticmethod
    def _unresolved(reason: str) -> Resolution:
        return Resolution(
            selected_settlement_id=None,
            decision="unresolved",
            confidence=0.0,
            reason=reason,
        )

    def resolve_many(self, cases: list[ResolutionCase]) -> ResolverRun:
        started = perf_counter()
        if not cases:
            return ResolverRun(resolutions={}, model_calls=0, latency_ms=0)

        prompt = {
            "task": "Resolve every case by comparing noisy reference identifiers. Choose only a candidate supplied for that order, otherwise abstain. Never invent an ID.",
            "cases": [self._safe_case(case) for case in cases],
        }
        expected = {case.order.order_id: case for case in cases}
        fallback_reason = (
            "Model resolution was unavailable and the record was left unresolved."
        )
        try:
            response = self.client.chat_completion(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a cautious settlement reconciliation assistant.",
                    },
                    {"role": "user", "content": json.dumps(prompt)},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "batch_resolution",
                        "schema": BatchResolution.model_json_schema(),
                        "strict": True,
                    },
                },
                max_tokens=1800,
            )
            parsed = BatchResolution.model_validate_json(
                response.choices[0].message.content
            )
            resolutions = self._validate_output(parsed.resolutions, expected)
        except (
            HfHubHTTPError,
            RequestException,
            ValidationError,
            AttributeError,
            IndexError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            resolutions = {
                order_id: self._unresolved(f"{fallback_reason} ({type(exc).__name__})")
                for order_id in expected
            }
        return ResolverRun(
            resolutions=resolutions,
            model_calls=1,
            latency_ms=round((perf_counter() - started) * 1000),
        )

    @staticmethod
    def _safe_case(case: ResolutionCase) -> dict[str, object]:
        return {
            "order": {
                "order_id": case.order.order_id,
                "payment_id": case.order.payment_id,
                "gross_amount": case.order.gross_amount,
                "created_at": case.order.created_at.isoformat(),
            },
            "candidates": [
                {
                    "settlement_id": item.settlement_id,
                    "reference": item.reference,
                    "gross_amount": item.gross_amount,
                    "fee": item.fee,
                    "tax": item.tax,
                    "net_amount": item.net_amount,
                    "settled_at": item.settled_at.isoformat(),
                }
                for item in case.candidates
            ],
        }

    def _validate_output(
        self,
        items: list[BatchResolutionItem],
        expected: dict[str, ResolutionCase],
    ) -> dict[str, Resolution]:
        output: dict[str, Resolution] = {}
        duplicates: set[str] = set()
        for item in items:
            if item.order_id in output:
                duplicates.add(item.order_id)
                continue
            case = expected.get(item.order_id)
            allowed_ids = (
                {candidate.settlement_id for candidate in case.candidates}
                if case
                else set()
            )
            if case and (
                item.selected_settlement_id is None
                or item.selected_settlement_id in allowed_ids
            ):
                output[item.order_id] = Resolution(
                    selected_settlement_id=item.selected_settlement_id,
                    decision=item.decision,
                    confidence=item.confidence,
                    reason=item.reason,
                )

        for order_id in expected:
            if order_id in duplicates or order_id not in output:
                output[order_id] = self._unresolved(
                    "The model response was missing, duplicated or outside the allowed candidate set."
                )
        return output


def configured_resolver() -> Resolver:
    token = os.getenv("HF_TOKEN")
    if not token:
        return HeuristicResolver()
    return HuggingFaceResolver(
        token=token,
        model=os.getenv("HF_MODEL", "Qwen/Qwen3-32B"),
        provider=os.getenv("HF_PROVIDER", "auto"),
        timeout=float(os.getenv("HF_TIMEOUT_SECONDS", "20")),
    )
