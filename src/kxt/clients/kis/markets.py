"""KRX instrument master loader (CSV-based, offline cacheable)."""

from __future__ import annotations

import csv
import io
import logging
import os

import httpx

from kxt.errors import KXTAPIError, KXTTransportError, KXTValidationError
from kxt.markets.master import CachedInstrumentMaster, Market
from kxt.models.enums import AssetClass, InstrumentType, MarketSegment, Venue
from kxt.models.market_data import InstrumentRef

logger = logging.getLogger("kxt.kis.markets")


class KRXInstrumentMaster(CachedInstrumentMaster):
    """KRX-backed instrument master loaded from a CSV endpoint."""

    slug = "krx"

    def __init__(
        self,
        *,
        refresh_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        cache_dir=None,
        clock=None,
    ) -> None:
        super().__init__(cache_dir=cache_dir, refresh_url=refresh_url, clock=clock)
        self._http = http_client
        self._owns_http = http_client is None

    def provider_name(self) -> str:
        return "krx"

    async def _download_raw(self) -> bytes:
        url = self._refresh_url or os.environ.get("KXT_MARKETS_REFRESH_URL")
        if not url:
            raise KXTValidationError(
                "refresh URL required: set KXT_MARKETS_REFRESH_URL or pass refresh_url"
            )
        client = self._http or httpx.AsyncClient(timeout=30.0)
        try:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
            except httpx.HTTPError as exc:
                raise KXTTransportError(
                    f"krx markets download failed: {exc}", provider="krx"
                ) from exc
        finally:
            if self._owns_http and client is not self._http:
                try:
                    await client.aclose()
                except Exception:  # pragma: no cover - best-effort
                    pass

    def _parse_raw(self, data: bytes) -> tuple[Market, ...]:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = data.decode("cp949")
            except UnicodeDecodeError as exc:
                raise KXTAPIError(
                    f"krx markets decode failed: {exc}", provider="krx"
                ) from exc
        try:
            reader = csv.DictReader(io.StringIO(text))
            out: list[Market] = []
            for row in reader:
                symbol = (
                    row.get("종목코드")
                    or row.get("단축코드")
                    or row.get("symbol")
                    or ""
                ).strip()
                if not symbol:
                    continue
                name = (
                    row.get("회사명") or row.get("한글명") or row.get("name") or ""
                ).strip() or None
                isin = (row.get("ISIN") or row.get("isin") or "").strip() or None
                seg_raw = (row.get("시장구분") or row.get("market") or "").strip().upper()
                seg: MarketSegment | None = None
                if "KOSPI" in seg_raw or "유가" in seg_raw or "코스피" in seg_raw:
                    seg = MarketSegment.KOSPI
                elif "KOSDAQ" in seg_raw or "코스닥" in seg_raw:
                    seg = MarketSegment.KOSDAQ
                elif "KONEX" in seg_raw or "코넥스" in seg_raw:
                    seg = MarketSegment.KONEX
                ir = InstrumentRef(
                    symbol=symbol,
                    venue=Venue.KRX,
                    market_segment=seg,
                    name=name,
                    isin=isin,
                    asset_class=AssetClass.EQUITY,
                    instrument_type=InstrumentType.COMMON_STOCK,
                )
                out.append(Market(instrument=ir))
            if not out:
                raise KXTAPIError(
                    "krx markets parse produced zero rows", provider="krx"
                )
            return tuple(out)
        except KXTAPIError:
            raise
        except Exception as exc:
            raise KXTAPIError(
                f"krx markets parse failed: {exc}", provider="krx"
            ) from exc
