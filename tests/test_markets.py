"""Instrument-master / markets smoke tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from kxt import MarketSegment
from kxt.clients.kis.markets import KRXInstrumentMaster
from kxt.errors import KXTTransportError, KXTValidationError


_KST = ZoneInfo("Asia/Seoul")


class _FakeKRXMaster(KRXInstrumentMaster):
    """KRXInstrumentMaster variant whose downloader is scripted in-memory."""

    def __init__(self, *, data: bytes, cache_dir: Path, clock=None) -> None:
        super().__init__(refresh_url="http://fake.invalid/markets", cache_dir=cache_dir, clock=clock)
        self._data = data
        self.download_calls = 0

    async def _download_raw(self) -> bytes:
        self.download_calls += 1
        return self._data


class _FailAfterFirstMaster(KRXInstrumentMaster):
    """Succeeds on the first download, then raises KXTTransportError."""

    def __init__(self, *, first_data: bytes, cache_dir: Path, clock=None) -> None:
        super().__init__(refresh_url="http://fake.invalid/markets", cache_dir=cache_dir, clock=clock)
        self._first = first_data
        self.calls = 0

    async def _download_raw(self) -> bytes:
        self.calls += 1
        if self.calls == 1:
            return self._first
        raise KXTTransportError("simulated transport failure", provider="krx")


async def test_markets_fetch_uses_cache_when_fresh(krx_fixture_csv, tmp_cache_dir):
    clock = lambda: datetime(2026, 1, 2, 9, 0, tzinfo=_KST)
    master = _FakeKRXMaster(data=krx_fixture_csv, cache_dir=tmp_cache_dir, clock=clock)

    first = await master.fetch_markets()
    second = await master.fetch_markets()

    assert master.download_calls == 1
    assert len(first) == 3
    assert first == second


async def test_markets_stale_fallback_on_download_error(krx_fixture_csv, tmp_cache_dir, caplog):
    clock = lambda: datetime(2026, 1, 2, 9, 0, tzinfo=_KST)
    master = _FailAfterFirstMaster(first_data=krx_fixture_csv, cache_dir=tmp_cache_dir, clock=clock)

    # First: successful download populates the on-disk cache.
    ok = await master.fetch_markets()
    assert len(ok) == 3

    with caplog.at_level("WARNING", logger="kxt.markets"):
        stale = await master.fetch_markets(refresh=True)

    assert stale == ok
    assert any("stale cache" in rec.message for rec in caplog.records)


async def test_resolve_instrument_populates_name_and_segment(krx_fixture_csv, tmp_cache_dir):
    clock = lambda: datetime(2026, 1, 2, 9, 0, tzinfo=_KST)
    master = _FakeKRXMaster(data=krx_fixture_csv, cache_dir=tmp_cache_dir, clock=clock)

    await master.fetch_markets()
    ref = await master.resolve_instrument("034020")

    assert ref.symbol == "034020"
    assert ref.name == "두산에너빌리티"
    assert ref.market_segment == MarketSegment.KOSPI


async def test_resolve_instrument_unknown_symbol_raises(krx_fixture_csv, tmp_cache_dir):
    clock = lambda: datetime(2026, 1, 2, 9, 0, tzinfo=_KST)
    master = _FakeKRXMaster(data=krx_fixture_csv, cache_dir=tmp_cache_dir, clock=clock)

    await master.fetch_markets()
    with pytest.raises(KXTValidationError):
        await master.resolve_instrument("999999")
