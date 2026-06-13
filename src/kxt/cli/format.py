"""Structured plain-text + JSON rendering for the kxt CLI.

This module owns the CLI output layer. Handlers hand DTOs here; we render
either a human/LLM-readable plain-text form (default) or a JSON form (opt-in
via the global `--json` flag). Only the plain-text path performs account
identifier masking; the JSON path never masks.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Iterable

from kxt.clients.capabilities import (
    CapabilitySupport,
    ClientCapabilities,
    MarketCapabilities,
    StreamCapabilities,
)
from kxt.models.api import (
    AccountOverviewResponse,
    AccountSummary,
    BarsResponse,
    BuyingPowerResponse,
    CancelOrderResponse,
    ConditionSearchesResponse,
    ConditionSearchResultsResponse,
    InvestorFlowResponse,
    InvestorTrendsResponse,
    ModifyOrderResponse,
    OpenOrdersResponse,
    OrderHistoryResponse,
    OrderBookResponse,
    PositionsResponse,
    ProviderOrderRef,
    QuoteResponse,
    QuotesResponse,
    RecentTradesResponse,
    ProgramTradeResponse,
    RankingsResponse,
    SubmitOrderResponse,
)


# ---------- JSON path --------------------------------------------------------


def _to_json(value: Any) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False, indent=2)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


# ---------- Shared helpers ---------------------------------------------------


def _term_width() -> int:
    try:
        return shutil.get_terminal_size((80, 24)).columns
    except Exception:
        return 80


def _mask_account(value: str | None) -> str:
    if value is None:
        return "-"
    digits = "".join(ch for ch in value if ch.isdigit())
    tail = digits[-4:] if len(digits) >= 4 else ""
    return f"****{tail}" if tail else "****"


def _yesno(value: bool | None) -> str:
    if value is None:
        return "-"
    return "yes" if value else "no"


def _fmt_scalar(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _render_kv_block(pairs: Iterable[tuple[str, Any]], indent: int = 0) -> list[str]:
    pairs = list(pairs)
    if not pairs:
        return []
    label_w = max(len(k) for k, _ in pairs)
    prefix = " " * indent
    return [f"{prefix}{k.ljust(label_w)} : {_fmt_scalar(v)}" for k, v in pairs]


def _render_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    min_col_sep: int = 2,
) -> list[str]:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if len(cell) > widths[i]:
                widths[i] = len(cell)
    sep = " " * min_col_sep
    header_line = sep.join(h.ljust(widths[i]) for i, h in enumerate(headers))
    divider = sep.join("-" * widths[i] for i in range(len(headers)))
    body = [sep.join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows]
    return [header_line, divider, *body]


def _table_fits(headers: list[str], rows: list[list[str]]) -> bool:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if len(cell) > widths[i]:
                widths[i] = len(cell)
    total = sum(widths) + 2 * (len(widths) - 1)
    return total <= _term_width()


# ---------- Capabilities -----------------------------------------------------


def _render_capability_support(value: Any) -> str:
    supported = getattr(value, "supported", None)
    if supported is True:
        return "supported"
    if supported is False:
        reason = getattr(value, "reason", None)
        return f"unsupported ({reason})" if reason else "unsupported"
    if isinstance(value, bool):
        return "supported" if value else "unsupported"
    return _fmt_scalar(value)


def _render_capability_group(group: Any) -> list[str]:
    lines: list[str] = []
    if not is_dataclass(group):
        return [f"  {_fmt_scalar(group)}"]
    for f in fields(group):
        v = getattr(group, f.name)
        lines.append(f"  {f.name}: {_render_capability_support(v)}")
    return lines


def _render_client_capabilities(caps: ClientCapabilities) -> str:
    lines: list[str] = []
    lines.append(f"Provider: {caps.provider}")
    lines.append(f"Requires credentials: {_yesno(caps.requires_credentials)}")
    if caps.supported_venues:
        lines.append("Venues: " + ", ".join(v.value for v in caps.supported_venues))
    if caps.supported_scopes:
        lines.append("Scopes: " + ", ".join(s.value for s in caps.supported_scopes))
    lines.append("")
    lines.append("Markets:")
    lines.extend(_render_capability_group(caps.market))
    lines.append("")
    lines.append("Streams:")
    lines.extend(_render_capability_group(caps.streams))
    lines.append("")
    lines.append(f"Trading: {_render_capability_support(caps.trading)}")
    lines.append(f"Native passthrough: {_render_capability_support(caps.native)}")
    if caps.notes:
        lines.append("")
        lines.append("Notes:")
        for n in caps.notes:
            lines.append(f"  - {n}")
    return "\n".join(lines)


# ---------- Market data DTOs -------------------------------------------------


def _render_quote(q: QuoteResponse) -> str:
    pairs = [
        ("occurred_at", q.occurred_at),
        ("last", q.last),
        ("open", q.open),
        ("high", q.high),
        ("low", q.low),
        ("previous_close", q.previous_close),
        ("change", q.change),
        ("change_rate", q.change_rate),
        ("volume", q.volume),
    ]
    return "\n".join(_render_kv_block(pairs))


def _render_quotes(resp: QuotesResponse) -> str:
    header = f"Quotes: {len(resp.quotes)}"
    if not resp.quotes:
        return header
    headers = ["symbol", "occurred_at", "last", "open", "high", "low", "volume"]
    rows = [
        [
            q.symbol,
            _fmt_scalar(q.occurred_at),
            _fmt_scalar(q.last),
            _fmt_scalar(q.open),
            _fmt_scalar(q.high),
            _fmt_scalar(q.low),
            _fmt_scalar(q.volume),
        ]
        for q in resp.quotes
    ]
    if _table_fits(headers, rows):
        return "\n".join([header, "", *_render_table(headers, rows)])
    blocks: list[str] = [header, ""]
    for q in resp.quotes:
        blocks.extend(
            _render_kv_block(
                [
                    ("symbol", q.symbol),
                    ("occurred_at", q.occurred_at),
                    ("last", q.last),
                    ("open", q.open),
                    ("high", q.high),
                    ("low", q.low),
                    ("volume", q.volume),
                ]
            )
        )
        blocks.append("")
    return "\n".join(blocks).rstrip()


def _render_bars(resp: BarsResponse) -> str:
    header = (
        f"Timeframe: {resp.timeframe}   "
        f"Bars: {len(resp.bars)}   "
        f"Adjusted: {_yesno(resp.adjusted)}"
    )
    if not resp.bars:
        return header
    headers = ["opened_at", "open", "high", "low", "close", "volume"]
    rows = [
        [
            _fmt_scalar(b.opened_at),
            _fmt_scalar(b.open),
            _fmt_scalar(b.high),
            _fmt_scalar(b.low),
            _fmt_scalar(b.close),
            _fmt_scalar(b.volume),
        ]
        for b in resp.bars
    ]
    if _term_width() >= 100 and _table_fits(headers, rows):
        return "\n".join([header, "", *_render_table(headers, rows)])
    # narrow fallback
    blocks: list[str] = [header, ""]
    for b in resp.bars:
        blocks.extend(
            _render_kv_block(
                [
                    ("opened_at", b.opened_at),
                    ("open", b.open),
                    ("high", b.high),
                    ("low", b.low),
                    ("close", b.close),
                    ("volume", b.volume),
                ]
            )
        )
        blocks.append("")
    return "\n".join(blocks).rstrip()


def _render_recent_trades(resp: RecentTradesResponse) -> str:
    header = f"Trades: {len(resp.trades)}"
    if not resp.trades:
        return header
    headers = ["occurred_at", "price", "quantity", "ask", "bid"]
    rows = [
        [
            _fmt_scalar(t.occurred_at),
            _fmt_scalar(t.price),
            _fmt_scalar(t.quantity),
            _fmt_scalar(t.ask_price),
            _fmt_scalar(t.bid_price),
        ]
        for t in resp.trades
    ]
    if _term_width() >= 80 and _table_fits(headers, rows):
        return "\n".join([header, "", *_render_table(headers, rows)])
    blocks = [header, ""]
    for t in resp.trades:
        blocks.extend(
            _render_kv_block(
                [
                    ("occurred_at", t.occurred_at),
                    ("price", t.price),
                    ("quantity", t.quantity),
                    ("ask", t.ask_price),
                    ("bid", t.bid_price),
                ]
            )
        )
        blocks.append("")
    return "\n".join(blocks).rstrip()


def _render_orderbook(resp: OrderBookResponse) -> str:
    header_pairs = [
        ("occurred_at", resp.occurred_at),
        ("total_ask_qty", resp.total_ask_quantity),
        ("total_bid_qty", resp.total_bid_quantity),
    ]
    head = _render_kv_block(header_pairs)
    asks = list(resp.asks)
    bids = list(resp.bids)
    depth = max(len(asks), len(bids))
    if depth == 0:
        return "\n".join(head)
    ask_rows = [[_fmt_scalar(lvl.price), _fmt_scalar(lvl.quantity)] for lvl in asks]
    bid_rows = [[_fmt_scalar(lvl.price), _fmt_scalar(lvl.quantity)] for lvl in bids]
    width = _term_width()
    # side-by-side rendering if wide enough
    if width >= 60 and depth <= 40:
        # Build each table independently
        ask_table = _render_table(["ask_price", "ask_qty"], ask_rows) if ask_rows else ["(no asks)"]
        bid_table = _render_table(["bid_price", "bid_qty"], bid_rows) if bid_rows else ["(no bids)"]
        left_w = max(len(line) for line in ask_table)
        combined: list[str] = []
        max_lines = max(len(ask_table), len(bid_table))
        combined.append("")
        for i in range(max_lines):
            left = ask_table[i] if i < len(ask_table) else ""
            right = bid_table[i] if i < len(bid_table) else ""
            combined.append(f"{left.ljust(left_w)}    {right}")
        if sum(len(x) for x in combined[1:2]) <= width:
            return "\n".join([*head, *combined])
    # narrow fallback: two stacked blocks
    lines = list(head)
    lines.append("")
    lines.append("Asks:")
    if ask_rows:
        lines.extend("  " + ln for ln in _render_table(["price", "quantity"], ask_rows))
    else:
        lines.append("  (empty)")
    lines.append("")
    lines.append("Bids:")
    if bid_rows:
        lines.extend("  " + ln for ln in _render_table(["price", "quantity"], bid_rows))
    else:
        lines.append("  (empty)")
    return "\n".join(lines)


def _render_investor_flow(resp: InvestorFlowResponse) -> str:
    head = [f"as_of_date: {_fmt_scalar(resp.as_of_date)}", ""]
    metrics = [
        "net_buy_quantity",
        "net_buy_notional",
        "buy_quantity",
        "sell_quantity",
    ]
    headers = ["metric", "retail", "foreign", "institution"]
    rows: list[list[str]] = []
    buckets = {"retail": resp.retail, "foreign": resp.foreign, "institution": resp.institution}
    for m in metrics:
        rows.append(
            [
                m,
                _fmt_scalar(getattr(buckets["retail"], m)),
                _fmt_scalar(getattr(buckets["foreign"], m)),
                _fmt_scalar(getattr(buckets["institution"], m)),
            ]
        )
    if _term_width() >= 80 and _table_fits(headers, rows):
        return "\n".join([*head, *_render_table(headers, rows)])
    # narrow fallback: per-bucket blocks
    lines = list(head)
    for name, bucket in buckets.items():
        lines.append(f"{name}:")
        lines.extend(
            _render_kv_block(
                [
                    ("net_buy_quantity", bucket.net_buy_quantity),
                    ("net_buy_notional", bucket.net_buy_notional),
                    ("buy_quantity", bucket.buy_quantity),
                    ("sell_quantity", bucket.sell_quantity),
                ],
                indent=2,
            )
        )
        lines.append("")
    return "\n".join(lines).rstrip()


def _render_rankings(resp: RankingsResponse) -> str:
    header = f"Rankings: {len(resp.entries)}"
    if not resp.entries:
        return header
    headers = ["rank", "symbol", "name", "price", "change_rate", "quantity", "value", "label"]
    rows = [
        [
            _fmt_scalar(e.rank),
            _fmt_scalar(e.symbol),
            _fmt_scalar(e.name),
            _fmt_scalar(e.price),
            _fmt_scalar(e.change_rate),
            _fmt_scalar(e.quantity),
            _fmt_scalar(e.value),
            _fmt_scalar(e.label),
        ]
        for e in resp.entries
    ]
    return "\n".join([header, "", *_render_table(headers, rows)])


def _render_program_trade(resp: ProgramTradeResponse) -> str:
    header = f"Program trades: {len(resp.records)}"
    if not resp.records:
        return header
    headers = ["occurred_at", "symbol", "sell_qty", "buy_qty", "net_qty", "net_notional"]
    rows = [
        [
            _fmt_scalar(r.occurred_at),
            _fmt_scalar(r.symbol),
            _fmt_scalar(r.sell_quantity),
            _fmt_scalar(r.buy_quantity),
            _fmt_scalar(r.net_buy_quantity),
            _fmt_scalar(r.net_buy_notional),
        ]
        for r in resp.records
    ]
    return "\n".join([header, "", *_render_table(headers, rows)])


def _render_condition_searches(resp: ConditionSearchesResponse) -> str:
    header = f"Condition searches: {len(resp.searches)}"
    if not resp.searches:
        return header
    return "\n".join([header, "", *_render_table(["seq", "name"], [[s.seq, _fmt_scalar(s.name)] for s in resp.searches])])


def _render_condition_results(resp: ConditionSearchResultsResponse) -> str:
    header = f"Condition results: {len(resp.results)}"
    if not resp.results:
        return header
    rows = [[r.symbol, _fmt_scalar(r.name), _fmt_scalar(r.price), _fmt_scalar(r.change_rate), _fmt_scalar(r.volume)] for r in resp.results]
    return "\n".join([header, "", *_render_table(["symbol", "name", "price", "change_rate", "volume"], rows)])


def _render_investor_trends(resp: InvestorTrendsResponse) -> str:
    header = f"Investor trends: {len(resp.records)}"
    if not resp.records:
        return header
    rows = [
        [
            _fmt_scalar(r.occurred_at),
            r.symbol,
            _fmt_scalar(r.category),
            _fmt_scalar(r.net_buy_quantity),
            _fmt_scalar(r.net_buy_notional),
        ]
        for r in resp.records
    ]
    return "\n".join([header, "", *_render_table(["occurred_at", "symbol", "category", "net_qty", "net_notional"], rows)])


# ---------- Account / trading DTOs -------------------------------------------


def _render_account_overview(resp: AccountOverviewResponse) -> str:
    eq = resp.equity
    equity_pairs = [
        ("account", _mask_account(eq.account.account_id) if eq.account else "-"),
        ("as_of", eq.as_of),
        ("cash", eq.cash),
        ("d1_settlement", eq.d1_settlement),
        ("d2_settlement", eq.d2_settlement),
        ("securities_value", eq.securities_value),
        ("total_value", eq.total_value),
        ("net_asset_value", eq.net_asset_value),
        ("total_cost_basis", eq.total_cost_basis),
        ("positions_market_value", eq.positions_market_value),
        ("total_unrealized_pnl", eq.total_unrealized_pnl),
        ("asset_change", eq.asset_change),
        ("asset_change_rate", eq.asset_change_rate),
    ]
    lines = ["Equity:"]
    lines.extend(_render_kv_block(equity_pairs, indent=2))
    lines.append("")
    lines.append(f"Positions: {len(resp.positions)}")
    if resp.positions:
        headers = [
            "symbol",
            "qty",
            "avg_price",
            "market_price",
            "market_value",
            "unrealized_pnl",
            "unrealized_pnl_rate",
        ]
        rows = [
            [
                _fmt_scalar(p.symbol),
                _fmt_scalar(p.quantity),
                _fmt_scalar(p.average_price),
                _fmt_scalar(p.market_price),
                _fmt_scalar(p.market_value),
                _fmt_scalar(p.unrealized_pnl),
                _fmt_scalar(p.unrealized_pnl_rate),
            ]
            for p in resp.positions
        ]
        if _term_width() >= 100 and _table_fits(headers, rows):
            lines.append("")
            lines.extend(_render_table(headers, rows))
        else:
            for p in resp.positions:
                lines.append("")
                lines.extend(
                    _render_kv_block(
                        [
                            ("symbol", p.symbol),
                            ("qty", p.quantity),
                            ("avg_price", p.average_price),
                            ("market_price", p.market_price),
                            ("market_value", p.market_value),
                            ("unrealized_pnl", p.unrealized_pnl),
                            ("unrealized_pnl_rate", p.unrealized_pnl_rate),
                        ],
                        indent=2,
                    )
                )
    lines.append("")
    lines.append(f"Cursor: {_yesno(resp.cursor is not None)}")
    return "\n".join(lines)


def _render_positions(resp: PositionsResponse) -> str:
    header = f"Positions: {len(resp.positions)}"
    if not resp.positions:
        return header
    headers = ["symbol", "qty", "avg_price", "market_price", "unrealized_pnl", "side"]
    rows = [
        [
            _fmt_scalar(p.symbol),
            _fmt_scalar(p.quantity),
            _fmt_scalar(p.average_price),
            _fmt_scalar(p.market_price),
            _fmt_scalar(p.unrealized_pnl),
            _fmt_scalar(p.side),
        ]
        for p in resp.positions
    ]
    if _term_width() >= 80 and _table_fits(headers, rows):
        return "\n".join([header, "", *_render_table(headers, rows)])
    lines = [header]
    for p in resp.positions:
        lines.append("")
        lines.extend(
            _render_kv_block(
                [
                    ("symbol", p.symbol),
                    ("qty", p.quantity),
                    ("avg_price", p.average_price),
                    ("market_price", p.market_price),
                    ("unrealized_pnl", p.unrealized_pnl),
                    ("side", p.side),
                ]
            )
        )
    return "\n".join(lines)


def _render_buying_power(resp: BuyingPowerResponse) -> str:
    s = resp.snapshot
    pairs = [(f.name, getattr(s, f.name)) for f in fields(s)]
    return "\n".join(_render_kv_block(pairs))


def _render_open_orders(resp: OpenOrdersResponse) -> str:
    head = f"Open orders: {len(resp.orders)}"
    if not resp.orders:
        return head
    blocks: list[str] = [head]
    sep = "-" * 40
    for i, o in enumerate(resp.orders):
        blocks.append(sep if i == 0 else sep)
        blocks.extend(
            _render_kv_block(
                [
                    ("order_id", o.order_ref.order_id),
                    ("account", _mask_account(o.order_ref.account_id)),
                    ("symbol", o.symbol),
                    ("side", o.side),
                    ("order_type", o.order_type),
                    ("state", o.state),
                    ("quantity", o.quantity),
                    ("remaining_quantity", o.remaining_quantity),
                    ("limit_price", o.limit_price),
                    ("filled_quantity", o.filled_quantity),
                    ("cancelable_quantity", o.cancelable_quantity),
                    ("occurred_at", o.occurred_at),
                ]
            )
        )
    blocks.append(sep)
    return "\n".join(blocks)


def _render_order_history(resp: OrderHistoryResponse) -> str:
    head = f"Records: {len(resp.records)}"
    blocks: list[str] = [head]
    sep = "-" * 40
    for r in resp.records:
        blocks.append(sep)
        blocks.extend(
            _render_kv_block(
                [
                    ("order_id", r.order_ref.order_id),
                    ("account", _mask_account(r.order_ref.account_id)),
                    ("symbol", r.symbol),
                    ("side", r.side),
                    ("order_type", r.order_type),
                    ("state", r.state),
                    ("quantity", r.quantity),
                    ("limit_price", r.limit_price),
                    ("filled_quantity", r.filled_quantity),
                    ("filled_notional", r.filled_notional),
                    ("average_fill_price", r.average_fill_price),
                    ("remaining_quantity", r.remaining_quantity),
                    ("order_date", r.order_date),
                    ("submitted_at", r.submitted_at),
                ]
            )
        )
    if resp.records:
        blocks.append(sep)
    if resp.summary is not None:
        blocks.append("")
        blocks.append("Summary:")
        blocks.extend(
            _render_kv_block(
                [
                    ("total_buy_quantity", resp.summary.total_buy_quantity),
                    ("total_sell_quantity", resp.summary.total_sell_quantity),
                    ("total_buy_notional", resp.summary.total_buy_notional),
                    ("total_sell_notional", resp.summary.total_sell_notional),
                ],
                indent=2,
            )
        )
    return "\n".join(blocks)


def _render_order_ack(resp: Any) -> str:
    ack = resp.acknowledgement
    account_id = ack.order_ref.account_id if ack.order_ref else None
    order_id = ack.order_ref.order_id if ack.order_ref else None
    return "\n".join(
        _render_kv_block(
            [
                ("order_id", order_id),
                ("account", _mask_account(account_id)),
                ("state", ack.state),
                ("occurred_at", ack.occurred_at),
                ("message", ack.message),
            ]
        )
    )


# ---------- Doctor dict ------------------------------------------------------


def _render_doctor(value: dict[str, Any]) -> str:
    lines: list[str] = []
    provider = value.get("provider", "-")
    ready = value.get("ready")
    lines.append(f"Provider: {provider}   Ready: {_yesno(bool(ready))}")
    creds = value.get("credential_env") or {}
    if creds:
        lines.append("")
        lines.append("Credentials:")
        for k, v in creds.items():
            lines.append(f"  {k}: {v}")
    checks = value.get("checks") or ()
    if checks:
        lines.append("")
        lines.append("Checks:")
        for c in checks:
            lines.append(f"  - {c}")
    notes = value.get("notes") or ()
    if notes:
        lines.append("")
        lines.append("Notes:")
        for n in notes:
            lines.append(f"  - {n}")
    return "\n".join(lines)


# ---------- Fallback ---------------------------------------------------------


def _render_fallback(value: Any) -> str:
    if value is None:
        return "-"
    if is_dataclass(value):
        pairs: list[tuple[str, Any]] = []
        nested: list[tuple[str, Any]] = []
        for f in fields(value):
            v = getattr(value, f.name)
            if is_dataclass(v) or (isinstance(v, (list, tuple)) and v and is_dataclass(v[0])):
                nested.append((f.name, v))
            else:
                pairs.append((f.name, v))
        lines = _render_kv_block(pairs)
        for name, v in nested:
            lines.append("")
            lines.append(f"{name}:")
            if isinstance(v, (list, tuple)):
                for i, item in enumerate(v):
                    lines.append(f"  [{i}]")
                    lines.append(_indent(_render_fallback(item), 4))
            else:
                lines.append(_indent(_render_fallback(v), 2))
        return "\n".join(lines)
    if isinstance(value, dict):
        return "\n".join(_render_kv_block(list(value.items())))
    if isinstance(value, (list, tuple)):
        return "\n".join(f"  - {_fmt_scalar(v)}" for v in value)
    return _fmt_scalar(value)


def _indent(text: str, n: int) -> str:
    prefix = " " * n
    return "\n".join(prefix + line for line in text.splitlines())


# ---------- Dispatch ---------------------------------------------------------


_RENDERERS: dict[type, Callable[[Any], str]] = {
    ClientCapabilities: _render_client_capabilities,
    QuoteResponse: _render_quote,
    QuotesResponse: _render_quotes,
    BarsResponse: _render_bars,
    RecentTradesResponse: _render_recent_trades,
    OrderBookResponse: _render_orderbook,
    InvestorFlowResponse: _render_investor_flow,
    RankingsResponse: _render_rankings,
    ProgramTradeResponse: _render_program_trade,
    ConditionSearchesResponse: _render_condition_searches,
    ConditionSearchResultsResponse: _render_condition_results,
    InvestorTrendsResponse: _render_investor_trends,
    AccountOverviewResponse: _render_account_overview,
    PositionsResponse: _render_positions,
    BuyingPowerResponse: _render_buying_power,
    OpenOrdersResponse: _render_open_orders,
    OrderHistoryResponse: _render_order_history,
    SubmitOrderResponse: _render_order_ack,
    CancelOrderResponse: _render_order_ack,
    ModifyOrderResponse: _render_order_ack,
}


def render_output(value: Any, *, as_json: bool) -> str:
    if as_json:
        return _to_json(value)
    renderer = _RENDERERS.get(type(value))
    if renderer is not None:
        return renderer(value)
    if isinstance(value, dict):
        # Heuristic: doctor-style dict
        if "provider" in value and "credential_env" in value:
            return _render_doctor(value)
        return _render_fallback(value)
    return _render_fallback(value)


__all__ = [
    "render_output",
    "_to_json",
    "_json_default",
    "_mask_account",
]
