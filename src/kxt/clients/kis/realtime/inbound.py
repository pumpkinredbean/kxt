"""Inbound frame demultiplexer for the KIS realtime websocket."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Optional

from ..parsing import (
    KIS_ORDERBOOK_WS_TR_ID,
    KIS_TRADE_TR_ID,
    parse_orderbook_event,
    parse_trade_event,
)
from .registry import SubscriptionRegistry
from .subscription import Subscription


class InboundPump:
    """Reads websocket frames and dispatches to ack/nack/event callbacks."""

    def __init__(
        self,
        *,
        ws_getter: Callable[[], Any],
        registry: SubscriptionRegistry,
        on_ack: Callable[[str, str], Awaitable[None]],
        on_nack: Callable[[str, str, str, str], Awaitable[None]],
        on_event: Callable[[Subscription, Any], Awaitable[None]],
        on_pingpong: Callable[[Any], Awaitable[None]],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._ws_getter = ws_getter
        self._registry = registry
        self._on_ack = on_ack
        self._on_nack = on_nack
        self._on_event = on_event
        self._on_pingpong = on_pingpong
        self._logger = logger or logging.getLogger("kxt.kis.realtime")

    async def run(self, stop_event: asyncio.Event) -> None:
        ws = self._ws_getter()
        if ws is None:
            return
        async for raw in ws:
            if stop_event.is_set():
                return
            text = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
            if not text:
                continue

            if text.startswith("{"):
                try:
                    payload = json.loads(text)
                except Exception:
                    self._logger.warning("invalid-json-frame")
                    continue
                header = payload.get("header") or {}
                tr_id = str(header.get("tr_id") or "")
                if tr_id == "PINGPONG":
                    await self._on_pingpong(raw)
                    continue
                body = payload.get("body") or {}
                tr_key = str(header.get("tr_key") or body.get("tr_key") or "")
                rt_cd = str(body.get("rt_cd", ""))
                msg_cd = str(body.get("msg_cd", ""))
                msg1 = str(body.get("msg1", ""))
                if rt_cd == "0":
                    await self._on_ack(tr_id, tr_key)
                else:
                    await self._on_nack(tr_id, tr_key, msg_cd, msg1)
                continue

            if text[0] not in ("0", "1"):
                self._logger.warning("unknown-frame-prefix")
                continue

            parts = text.split("|", 3)
            if len(parts) < 4:
                self._logger.warning("short-frame")
                continue
            encrypt_flag, tr_id, _cnt, field_body = parts[0], parts[1], parts[2], parts[3]
            if encrypt_flag == "1":
                self._logger.warning("encrypted-frame-skipped tr_id=%s", tr_id)
                continue

            first_sep = field_body.find("^")
            symbol = field_body if first_sep == -1 else field_body[:first_sep]
            entry = self._registry.get(tr_id, symbol)
            if entry is None:
                continue

            try:
                if tr_id == KIS_TRADE_TR_ID:
                    event = parse_trade_event(text, instrument=entry.subscription.instrument)
                elif tr_id == KIS_ORDERBOOK_WS_TR_ID:
                    event = parse_orderbook_event(text, instrument=entry.subscription.instrument)
                else:
                    self._logger.warning("unknown-tr_id %s", tr_id)
                    continue
            except Exception as exc:  # parse errors are non-fatal
                self._logger.warning("parse-error tr_id=%s: %s", tr_id, exc)
                continue

            if event is None:
                continue
            await self._on_event(entry.subscription, event)
