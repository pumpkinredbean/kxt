"""Instrument master base classes and the :class:`Market` value type."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from kxt.errors import KXTAPIError, KXTTransportError, KXTValidationError
from kxt.models.enums import AssetClass, InstrumentType, MarketSegment, Venue
from kxt.models.market_data import InstrumentRef

logger = logging.getLogger("kxt.markets")

_KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True, slots=True)
class Market:
    """Listing metadata for a single tradable instrument."""

    instrument: InstrumentRef
    listed_on: date | None = None
    delisted_on: date | None = None
    lot_size: int | None = None
    tick_size: Decimal | None = None


class InstrumentMaster(ABC):
    """Abstract instrument master contract."""

    @abstractmethod
    async def fetch_markets(self, *, refresh: bool = False) -> tuple[Market, ...]:
        ...

    @abstractmethod
    async def resolve_instrument(
        self, symbol: str, *, venue: Venue | None = None
    ) -> InstrumentRef:
        ...


def _user_cache_dir() -> Path:
    """Return the per-user cache directory (mirrors KISTransport semantics)."""

    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg).expanduser()
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local)
        return Path.home() / "AppData" / "Local"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches"
    return Path.home() / ".cache"


def _atomic_write_json(path: Path, payload: object) -> None:
    """Atomically write JSON to ``path`` with 0600 permissions."""

    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        parent.chmod(0o700)
    except OSError:
        pass
    tmp_name: str | None = None
    try:
        fh = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=path.name + ".",
            delete=False,
        )
        tmp_name = fh.name
        try:
            json.dump(payload, fh, ensure_ascii=False, default=str)
            fh.flush()
            try:
                os.fchmod(fh.fileno(), 0o600)
            except OSError:
                pass
        finally:
            fh.close()
        Path(tmp_name).replace(path)
        tmp_name = None
        try:
            path.chmod(0o600)
        except OSError:
            pass
    finally:
        if tmp_name is not None:
            try:
                Path(tmp_name).unlink()
            except OSError:
                pass


class CachedInstrumentMaster(InstrumentMaster):
    """Cache-aware :class:`InstrumentMaster` that persists results as JSON.

    Cache layout::

        <cache_dir>/kxt/markets/<slug>-YYYYMMDD.json  (0600, atomic)

    TTL: valid until the next KST calendar midnight after file creation.
    """

    slug: str = "markets"

    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        refresh_url: str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._cache_root = (cache_dir or _user_cache_dir()) / "kxt" / "markets"
        self._refresh_url = refresh_url
        self._clock = clock or (lambda: datetime.now(tz=_KST))
        self._lock = asyncio.Lock()
        self._in_memory: tuple[Market, ...] | None = None
        self._in_memory_date: date | None = None

    # ------- public -------
    async def fetch_markets(self, *, refresh: bool = False) -> tuple[Market, ...]:
        async with self._lock:
            now = self._clock()
            now_kst = now.astimezone(_KST) if now.tzinfo else now.replace(tzinfo=_KST)
            today = now_kst.date()
            cached_path = self._cache_path(today)

            if (
                not refresh
                and self._in_memory is not None
                and self._in_memory_date == today
            ):
                return self._in_memory

            if not refresh:
                cached = self._try_load(cached_path)
                if cached is not None:
                    self._in_memory, self._in_memory_date = cached, today
                    return cached
                latest = self._latest_cache()
                if latest is not None:
                    markets = self._try_load(latest)
                    if markets is not None:
                        self._in_memory, self._in_memory_date = markets, today
                        return markets

            # need to download
            try:
                raw = await self._download_raw()
            except KXTTransportError:
                stale = self._latest_cache()
                if stale is not None:
                    fallback = self._try_load(stale)
                    if fallback is not None:
                        logger.warning(
                            "markets download failed; returning stale cache %s",
                            stale,
                        )
                        self._in_memory = fallback
                        self._in_memory_date = today
                        return fallback
                raise

            try:
                markets = self._parse_raw(raw)
            except KXTAPIError:
                raise
            except Exception as exc:  # pragma: no cover - defensive guard
                raise KXTAPIError(
                    f"markets parse failed: {exc}",
                    provider=self.provider_name(),
                ) from exc

            try:
                payload = {
                    "generated_at": now_kst.isoformat(),
                    "markets": [self._market_to_dict(m) for m in markets],
                }
                _atomic_write_json(cached_path, payload)
            except OSError as exc:
                logger.warning("markets cache write failed: %s", exc)

            self._in_memory = tuple(markets)
            self._in_memory_date = today
            return self._in_memory

    async def resolve_instrument(
        self, symbol: str, *, venue: Venue | None = None
    ) -> InstrumentRef:
        markets = await self.fetch_markets()
        needle = symbol.strip()
        for m in markets:
            if m.instrument.symbol == needle and (
                venue is None or m.instrument.venue == venue
            ):
                return m.instrument
        raise KXTValidationError(f"unknown symbol: {symbol!r}")

    # ------- abstract hooks -------
    @abstractmethod
    async def _download_raw(self) -> bytes:
        ...

    @abstractmethod
    def _parse_raw(self, data: bytes) -> tuple[Market, ...]:
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...

    # ------- helpers -------
    def _cache_path(self, today: date) -> Path:
        return self._cache_root / f"{self.slug}-{today.strftime('%Y%m%d')}.json"

    def _latest_cache(self) -> Path | None:
        try:
            if not self._cache_root.exists():
                return None
            files = sorted(self._cache_root.glob(f"{self.slug}-*.json"))
            return files[-1] if files else None
        except OSError:
            return None

    def _try_load(self, path: Path) -> tuple[Market, ...] | None:
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            return tuple(self._market_from_dict(d) for d in data.get("markets", []))
        except (
            FileNotFoundError,
            OSError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
            KeyError,
        ):
            return None

    @staticmethod
    def _market_to_dict(m: Market) -> dict:
        ir = m.instrument
        return {
            "instrument": {
                "symbol": ir.symbol,
                "venue": ir.venue.value if ir.venue else None,
                "market_segment": (
                    ir.market_segment.value if ir.market_segment else None
                ),
                "instrument_id": ir.instrument_id,
                "name": ir.name,
                "isin": ir.isin,
                "asset_class": ir.asset_class.value if ir.asset_class else None,
                "instrument_type": (
                    ir.instrument_type.value if ir.instrument_type else None
                ),
            },
            "listed_on": m.listed_on.isoformat() if m.listed_on else None,
            "delisted_on": m.delisted_on.isoformat() if m.delisted_on else None,
            "lot_size": m.lot_size,
            "tick_size": str(m.tick_size) if m.tick_size is not None else None,
        }

    @staticmethod
    def _market_from_dict(d: dict) -> Market:
        ird = d["instrument"]
        ir = InstrumentRef(
            symbol=ird["symbol"],
            venue=Venue(ird["venue"]) if ird.get("venue") else None,
            market_segment=(
                MarketSegment(ird["market_segment"])
                if ird.get("market_segment")
                else None
            ),
            instrument_id=ird.get("instrument_id"),
            name=ird.get("name"),
            isin=ird.get("isin"),
            asset_class=AssetClass(ird["asset_class"]) if ird.get("asset_class") else None,
            instrument_type=(
                InstrumentType(ird["instrument_type"])
                if ird.get("instrument_type")
                else None
            ),
        )
        return Market(
            instrument=ir,
            listed_on=date.fromisoformat(d["listed_on"]) if d.get("listed_on") else None,
            delisted_on=(
                date.fromisoformat(d["delisted_on"]) if d.get("delisted_on") else None
            ),
            lot_size=d.get("lot_size"),
            tick_size=Decimal(d["tick_size"]) if d.get("tick_size") else None,
        )
