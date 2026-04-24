"""Lightweight fake KIS-style websocket server for tests.

Protocol summary modeled after the KIS realtime websocket:

- Client subscribes/unsubscribes via JSON frames with
  ``{"header": {"tr_type": "1"|"2", ...}, "body": {"input": {"tr_id": ..., "tr_key": ...}}}``.
- The server auto-ACKs subscribe frames with
  ``{"header": {"tr_id": ..., "tr_key": ...}, "body": {"rt_cd": "0", "msg_cd": "OPSP0000", "msg1": "ok"}}``.
- Realtime events are pipe-delimited text frames:
  ``"0|<tr_id>|<count>|<^-joined field values>"``.

The server is intentionally minimal: it records every received message, counts
subscribe/unsubscribe calls, and exposes manual hooks for sending trade/order
book events and force-dropping the active connection.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets

from kxt.clients.kis.parsing import (
    KIS_ORDERBOOK_FIELDS,
    KIS_ORDERBOOK_WS_TR_ID,
    KIS_MARKET_STATUS_FIELDS,
    KIS_MARKET_STATUS_KRX_WS_TR_ID,
    KIS_MEMBER_FIELDS,
    KIS_MEMBER_KRX_WS_TR_ID,
    KIS_PROGRAM_TRADE_FIELDS,
    KIS_PROGRAM_TRADE_KRX_WS_TR_ID,
    KIS_TRADE_FIELDS,
    KIS_TRADE_TR_ID,
)


class FakeKISWSServer:
    """Async context manager wrapping a local websocket server on 127.0.0.1."""

    def __init__(self, *, auto_ack: bool = True) -> None:
        self._auto_ack = auto_ack
        self._server: Any = None
        self._url: str | None = None
        self._clients: list[Any] = []
        self._received: list[dict[str, Any]] = []
        self._sub_count = 0
        self._unsub_count = 0

    async def __aenter__(self) -> str:
        self._server = await websockets.serve(self._handler, "127.0.0.1", 0)
        sock = next(iter(self._server.sockets))
        port = sock.getsockname()[1]
        self._url = f"ws://127.0.0.1:{port}"
        return self._url

    async def __aexit__(self, exc_type, exc, tb) -> None:
        for ws in list(self._clients):
            try:
                await ws.close()
            except Exception:
                pass
        self._clients.clear()
        self._server.close()
        await self._server.wait_closed()

    # ---- inspection ----

    @property
    def received(self) -> list[dict[str, Any]]:
        return list(self._received)

    @property
    def subscribe_count(self) -> int:
        return self._sub_count

    @property
    def unsubscribe_count(self) -> int:
        return self._unsub_count

    def subscribe_messages_for(self, tr_key: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in self._received:
            header = msg.get("header") or {}
            body = (msg.get("body") or {}).get("input") or {}
            if header.get("tr_type") == "1" and body.get("tr_key") == tr_key:
                out.append(msg)
        return out

    # ---- scripting ----

    async def send_trade_event(
        self,
        symbol: str,
        *,
        price: str = "70000",
        qty: str = "1",
        occurred_time: str = "093000",
        occurred_date: str = "20260417",
    ) -> None:
        fields = {
            "MKSC_SHRN_ISCD": symbol,
            "STCK_CNTG_HOUR": occurred_time,
            "STCK_PRPR": price,
            "CNTG_VOL": qty,
            "BSOP_DATE": occurred_date,
            "CTTR": "seq-1",
            "CCLD_DVSN": "1",
        }
        body = "^".join(str(fields.get(f, "")) for f in KIS_TRADE_FIELDS)
        frame = f"0|{KIS_TRADE_TR_ID}|001|{body}"
        await self._broadcast(frame)

    async def send_orderbook_event(self, symbol: str) -> None:
        fields: dict[str, str] = {f: "" for f in KIS_ORDERBOOK_FIELDS}
        fields["MKSC_SHRN_ISCD"] = symbol
        fields["BSOP_HOUR"] = "093000"
        for i in range(1, 11):
            fields[f"ASKP{i}"] = str(70000 + i)
            fields[f"BIDP{i}"] = str(70000 - i)
            fields[f"ASKP_RSQN{i}"] = "10"
            fields[f"BIDP_RSQN{i}"] = "10"
        body = "^".join(fields[f] for f in KIS_ORDERBOOK_FIELDS)
        frame = f"0|{KIS_ORDERBOOK_WS_TR_ID}|001|{body}"
        await self._broadcast(frame)

    async def send_program_trade_event(self, symbol: str) -> None:
        fields = {f: "" for f in KIS_PROGRAM_TRADE_FIELDS}
        fields.update(
            {
                "MKSC_SHRN_ISCD": symbol,
                "STCK_CNTG_HOUR": "093000",
                "SELN_CNQN": "10",
                "SELN_TR_PBMN": "700000",
                "SHNU_CNQN": "15",
                "SHNU_TR_PBMN": "1050000",
                "NTBY_CNQN": "5",
                "NTBY_TR_PBMN": "350000",
            }
        )
        body = "^".join(fields[f] for f in KIS_PROGRAM_TRADE_FIELDS)
        await self._broadcast(f"0|{KIS_PROGRAM_TRADE_KRX_WS_TR_ID}|001|{body}")

    async def send_member_flow_event(self, symbol: str) -> None:
        fields = {f: "" for f in KIS_MEMBER_FIELDS}
        fields.update(
            {
                "MKSC_SHRN_ISCD": symbol,
                "SELN2_MBCR_NAME1": "SELLER",
                "BYOV_MBCR_NAME1": "BUYER",
                "TOTAL_SELN_QTY1": "10",
                "TOTAL_SHNU_QTY1": "15",
            }
        )
        body = "^".join(fields[f] for f in KIS_MEMBER_FIELDS)
        await self._broadcast(f"0|{KIS_MEMBER_KRX_WS_TR_ID}|001|{body}")

    async def send_market_status_event(self, symbol: str) -> None:
        fields = {f: "" for f in KIS_MARKET_STATUS_FIELDS}
        fields.update(
            {
                "MKSC_SHRN_ISCD": symbol,
                "TRHT_YN": "N",
                "MKOP_CLS_CODE": "2",
                "EXCH_CLS_CODE": "KRX",
            }
        )
        body = "^".join(fields[f] for f in KIS_MARKET_STATUS_FIELDS)
        await self._broadcast(f"0|{KIS_MARKET_STATUS_KRX_WS_TR_ID}|001|{body}")

    async def drop(self) -> None:
        """Forcefully close all active client connections."""

        for ws in list(self._clients):
            try:
                # Abort the underlying transport for a hard drop (simulates
                # connection loss). websockets' ``close`` helpers negotiate a
                # graceful close which some servers block on; aborting the
                # socket is closer to a real dropped connection.
                ws.transport.abort()
            except Exception:
                try:
                    await ws.close()
                except Exception:
                    pass
        self._clients.clear()

    # ---- internals ----

    async def _broadcast(self, frame: str) -> None:
        for ws in list(self._clients):
            try:
                await ws.send(frame)
            except Exception:
                pass

    async def _handler(self, ws) -> None:
        self._clients.append(ws)
        try:
            async for raw in ws:
                try:
                    text = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw
                    data = json.loads(text)
                except Exception:
                    continue
                self._received.append(data)
                header = data.get("header") or {}
                tr_type = str(header.get("tr_type") or "")
                body_input = ((data.get("body") or {}).get("input")) or {}
                tr_id = str(body_input.get("tr_id") or "")
                tr_key = str(body_input.get("tr_key") or "")
                if tr_type == "1":
                    self._sub_count += 1
                    if self._auto_ack:
                        await ws.send(
                            json.dumps(
                                {
                                    "header": {"tr_id": tr_id, "tr_key": tr_key},
                                    "body": {
                                        "rt_cd": "0",
                                        "msg_cd": "OPSP0000",
                                        "msg1": "ok",
                                    },
                                }
                            )
                        )
                elif tr_type == "2":
                    self._unsub_count += 1
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass
        finally:
            if ws in self._clients:
                self._clients.remove(ws)
