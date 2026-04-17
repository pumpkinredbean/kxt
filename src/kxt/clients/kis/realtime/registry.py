"""Subscription registry used by the KIS realtime session for reference
counting and ack/nack tracking per (tr_id, tr_key)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .subscription import Subscription


@dataclass
class _Entry:
    subscription: Subscription
    ref_count: int = 1
    ack_state: str = "pending"  # "pending" | "acked" | "failed" | "permanently_failed"
    attempts: int = 0
    last_error: Optional[tuple[str, str]] = field(default=None)


class SubscriptionRegistry:
    """Indexes active subscriptions by ``(tr_id, tr_key)``."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], _Entry] = {}

    def get(self, tr_id: str, tr_key: str) -> Optional[_Entry]:
        return self._entries.get((tr_id, tr_key))

    def add(self, sub: Subscription) -> tuple[_Entry, bool]:
        """Add or ref-count a subscription.

        Returns ``(entry, needs_subscribe)``.
        """

        key = (sub.tr_id, sub.tr_key)
        existing = self._entries.get(key)
        if existing is None:
            entry = _Entry(subscription=sub, ref_count=1, ack_state="pending", attempts=0)
            self._entries[key] = entry
            return entry, True
        existing.ref_count += 1
        return existing, False

    def remove(self, tr_id: str, tr_key: str) -> tuple[Optional[_Entry], bool]:
        """Decrement ref count. Returns ``(entry, needs_unsubscribe)``."""

        entry = self._entries.get((tr_id, tr_key))
        if entry is None:
            return None, False
        entry.ref_count -= 1
        if entry.ref_count <= 0:
            del self._entries[(tr_id, tr_key)]
            return entry, True
        return entry, False

    def alive_entries(self) -> list[_Entry]:
        return [e for e in self._entries.values() if e.ack_state != "permanently_failed"]

    def all_entries(self) -> list[_Entry]:
        return list(self._entries.values())

    def mark_ack(self, tr_id: str, tr_key: str) -> None:
        entry = self._entries.get((tr_id, tr_key))
        if entry is not None:
            entry.ack_state = "acked"
            entry.attempts = 0

    def mark_nack(self, tr_id: str, tr_key: str, rt_cd: str | None, msg: str | None) -> None:
        entry = self._entries.get((tr_id, tr_key))
        if entry is not None:
            entry.ack_state = "failed"
            entry.attempts += 1
            entry.last_error = (rt_cd or "", msg or "")

    def reset_pending_for_replay(self) -> list[_Entry]:
        alive = self.alive_entries()
        for entry in alive:
            entry.ack_state = "pending"
        return alive

    def purge_permanent(self, tr_id: str, tr_key: str) -> None:
        self._entries.pop((tr_id, tr_key), None)
