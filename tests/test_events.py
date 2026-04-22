"""Event-model smoke tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from kxt import TradeEvent


def test_event_trade_has_instrument():
    te = TradeEvent(
        occurred_at=datetime(2026, 4, 17, 9, 30, tzinfo=UTC),
        symbol="005930",
        price=Decimal("70000"),
        quantity=Decimal("1"),
    )
    assert te.symbol == "005930"
    assert te.price == Decimal("70000")
