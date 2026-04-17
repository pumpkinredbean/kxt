"""Event-model smoke tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from kxt import InstrumentRef, TradeEvent, Venue


def test_event_trade_has_instrument():
    instrument = InstrumentRef(symbol="005930", venue=Venue.KRX)
    te = TradeEvent(
        occurred_at=datetime(2026, 4, 17, 9, 30, tzinfo=UTC),
        instrument=instrument,
        price=Decimal("70000"),
        quantity=Decimal("1"),
    )
    assert te.instrument.symbol == "005930"
    assert te.instrument.venue == Venue.KRX
    assert te.price == Decimal("70000")
