"""Outbound command pump for the KIS realtime session.

Serializes subscribe / unsubscribe / resubscribe-all / shutdown commands onto
the active websocket with simple coalescing of adjacent subscribe/unsubscribe
pairs for the same ``(tr_id, tr_key)``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from ..parsing import websocket_subscription_message
from .registry import SubscriptionRegistry


@dataclass
class OutboundCommand:
    """A command destined for the KIS websocket."""

    kind: str  # "subscribe" | "unsubscribe" | "resubscribe_all" | "shutdown"
    tr_id: Optional[str] = None
    tr_key: Optional[str] = None


class OutboundPump:
    """Single consumer draining an outbound command queue to the websocket."""

    def __init__(
        self,
        *,
        ws_getter: Callable[[], Any],
        registry: SubscriptionRegistry,
        approval_key_getter: Callable[[], Awaitable[str]],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._ws_getter = ws_getter
        self._registry = registry
        self._get_approval = approval_key_getter
        self._logger = logger or logging.getLogger("kxt.kis.realtime")
        self._queue: asyncio.Queue[OutboundCommand] = asyncio.Queue()

    async def enqueue(self, cmd: OutboundCommand) -> None:
        await self._queue.put(cmd)

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            first = await self._queue.get()
            buf: list[OutboundCommand] = [first]
            while True:
                try:
                    buf.append(self._queue.get_nowait())
                except asyncio.QueueEmpty:
                    break

            coalesced: list[OutboundCommand] = []
            i = 0
            while i < len(buf):
                if (
                    i + 1 < len(buf)
                    and buf[i].kind == "subscribe"
                    and buf[i + 1].kind == "unsubscribe"
                    and buf[i].tr_id == buf[i + 1].tr_id
                    and buf[i].tr_key == buf[i + 1].tr_key
                ):
                    i += 2
                    continue
                coalesced.append(buf[i])
                i += 1

            for cmd in coalesced:
                if stop_event.is_set():
                    return
                if cmd.kind == "shutdown":
                    return
                ws = self._ws_getter()
                if ws is None:
                    continue
                approval = await self._get_approval()
                if cmd.kind == "subscribe":
                    if not cmd.tr_id or cmd.tr_key is None:
                        continue
                    msg = websocket_subscription_message(
                        approval_key=approval,
                        symbol=cmd.tr_key,
                        tr_id=cmd.tr_id,
                        tr_type="1",
                    )
                    await ws.send(json.dumps(msg))
                elif cmd.kind == "unsubscribe":
                    if not cmd.tr_id or cmd.tr_key is None:
                        continue
                    msg = websocket_subscription_message(
                        approval_key=approval,
                        symbol=cmd.tr_key,
                        tr_id=cmd.tr_id,
                        tr_type="2",
                    )
                    await ws.send(json.dumps(msg))
                elif cmd.kind == "resubscribe_all":
                    for entry in self._registry.alive_entries():
                        if stop_event.is_set():
                            return
                        sub = entry.subscription
                        replay = websocket_subscription_message(
                            approval_key=approval,
                            symbol=sub.tr_key,
                            tr_id=sub.tr_id,
                            tr_type="1",
                        )
                        await ws.send(json.dumps(replay))
                        await asyncio.sleep(0.01)
                else:
                    self._logger.warning("unknown outbound command kind=%s", cmd.kind)
