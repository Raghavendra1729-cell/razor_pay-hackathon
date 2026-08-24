from __future__ import annotations

from datetime import date, timedelta

from .models import BankDeposit, MerchantOrder, Settlement


def demo_batch() -> tuple[list[MerchantOrder], list[Settlement], list[BankDeposit], dict[str, tuple[str, str]]]:
    """Return a deterministic, labelled settlement batch for demos and tests.

    The first 48 orders are directly matchable. The next 12 have deliberately
    messy references and are intended for the constrained AI-resolution path.
    The remaining 12 records model real exceptions and should stay unresolved.
    """
    orders: list[MerchantOrder] = []
    settlements: list[Settlement] = []
    deposits: list[BankDeposit] = []
    ground_truth: dict[str, tuple[str, str]] = {}
    start = date(2026, 8, 1)

    for index in range(1, 73):
        created_at = start + timedelta(days=(index - 1) % 8)
        gross_amount = 7_500 + index * 1_237
        order = MerchantOrder(
            order_id=f"order_{index:04d}",
            payment_id=f"pay_demo_{index:04d}",
            customer_label=f"Merchant customer {index:02d}",
            gross_amount=gross_amount,
            created_at=created_at,
        )
        orders.append(order)

        if index > 60:
            continue

        fee = (gross_amount * 2) // 100
        tax = (fee * 18) // 100
        net_amount = gross_amount - fee - tax
        settlement_id = f"setl_{index:04d}"
        bank_txn_id = f"bank_{index:04d}"
        reference = order.payment_id if index <= 48 else f"batch-{created_at:%m%d}-{index:02d}"
        settlement = Settlement(
            settlement_id=settlement_id,
            reference=reference,
            gross_amount=gross_amount,
            fee=fee,
            tax=tax,
            net_amount=net_amount,
            settled_at=created_at + timedelta(days=1),
        )
        settlements.append(settlement)
        deposits.append(
            BankDeposit(
                bank_txn_id=bank_txn_id,
                narration=f"RAZORPAY SETTLEMENT {settlement_id.upper()}",
                amount=net_amount,
                posted_at=created_at + timedelta(days=2),
            )
        )
        ground_truth[order.order_id] = (settlement_id, bank_txn_id)

    # Add noisy source rows that a finance controller must not force-match.
    settlements.append(
        Settlement(
            settlement_id="setl_fee_variance",
            reference="pay_demo_0061",
            gross_amount=orders[60].gross_amount,
            fee=0,
            tax=0,
            net_amount=orders[60].gross_amount - 900,
            settled_at=start + timedelta(days=3),
        )
    )
    deposits.append(
        BankDeposit(
            bank_txn_id="bank_fee_variance",
            narration="RAZORPAY SETTLEMENT SETL_FEE_VARIANCE",
            amount=orders[60].gross_amount - 900,
            posted_at=start + timedelta(days=4),
        )
    )
    deposits.extend(
        [
            BankDeposit(
                bank_txn_id="bank_duplicate_a",
                narration="RAZORPAY SETTLEMENT UNKNOWN BATCH",
                amount=orders[69].gross_amount,
                posted_at=start + timedelta(days=5),
            ),
            BankDeposit(
                bank_txn_id="bank_duplicate_b",
                narration="RAZORPAY SETTLEMENT UNKNOWN BATCH",
                amount=orders[69].gross_amount,
                posted_at=start + timedelta(days=5),
            ),
        ]
    )
    return orders, settlements, deposits, ground_truth
