from __future__ import annotations

import json
import os
from typing import Protocol

from huggingface_hub.utils import HfHubHTTPError
from pydantic import ValidationError
from requests import RequestException

from .models import MerchantOrder, Resolution, Settlement


class Resolver(Protocol):
    mode: str

    def resolve(
        self, order: MerchantOrder, candidates: list[Settlement]
    ) -> Resolution: ...


class HeuristicResolver:
    """Safe local fallback: it only picks a single already-constrained candidate."""

    mode = "Deterministic fallback (HF token not configured)"

    def resolve(self, order: MerchantOrder, candidates: list[Settlement]) -> Resolution:
        if len(candidates) == 1:
            candidate = candidates[0]
            return Resolution(
                selected_settlement_id=candidate.settlement_id,
                decision="match",
                confidence=0.74,
                reason="One settlement satisfies the amount and settlement-window constraints.",
            )
        return Resolution(
            selected_settlement_id=None,
            decision="unresolved",
            confidence=0.0,
            reason="No unique, verifiable settlement candidate is available.",
        )


class HuggingFaceResolver:
    mode = "Hugging Face structured output"

    def __init__(self, token: str, model: str) -> None:
        from huggingface_hub import InferenceClient

        self.client = InferenceClient(api_key=token, provider="auto")
        self.model = model

    def resolve(self, order: MerchantOrder, candidates: list[Settlement]) -> Resolution:
        safe_candidates = [
            {
                "settlement_id": item.settlement_id,
                "reference": item.reference,
                "gross_amount": item.gross_amount,
                "fee": item.fee,
                "tax": item.tax,
                "net_amount": item.net_amount,
                "settled_at": item.settled_at.isoformat(),
            }
            for item in candidates
        ]
        prompt = {
            "task": "Choose one settlement only when the supplied evidence supports it. Never invent an ID.",
            "order": {
                "order_id": order.order_id,
                "payment_id": order.payment_id,
                "gross_amount": order.gross_amount,
                "created_at": order.created_at.isoformat(),
            },
            "candidates": safe_candidates,
        }
        schema = Resolution.model_json_schema()
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
                        "name": "resolution",
                        "schema": schema,
                        "strict": True,
                    },
                },
                max_tokens=240,
            )
            return Resolution.model_validate_json(response.choices[0].message.content)
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
            return Resolution(
                selected_settlement_id=None,
                decision="unresolved",
                confidence=0.0,
                reason=f"Model resolution was unavailable and the record was left unresolved: {type(exc).__name__}.",
            )


def configured_resolver() -> Resolver:
    token = os.getenv("HF_TOKEN")
    if not token:
        return HeuristicResolver()
    return HuggingFaceResolver(
        token=token, model=os.getenv("HF_MODEL", "Qwen/Qwen3-32B")
    )
