"""CLI output and surface tests for kxt.

These tests exercise the CLI in-process via ``kxt.cli.main.main``. No
network calls; authenticated commands are reached by monkeypatching
``_build_kis_client`` to return an async-context-manager stub.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from kxt.cli import format as cli_format
from kxt.cli import main as cli_main
from kxt.models.api import (
    AccountEquitySnapshot,
    AccountOverviewResponse,
    AccountSummary,
    BarsResponse,
    InvestorFlowBucket,
    InvestorFlowResponse,
    OpenOrder,
    OpenOrdersResponse,
    OrderBookResponse,
    PositionLot,
    PositionsResponse,
    ProviderOrderRef,
    ProviderRef,
    QuoteResponse,
    RecentTradesResponse,
    TradePrint,
)
from kxt.models.enums import OrderLifecycleState, OrderSide, OrderType
from kxt.models.market_data import InstrumentRef, QuoteLevel
from kxt.models.api import Bar


# ---------- help surface -----------------------------------------------------


def test_top_level_help_does_not_mention_removed_commands(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["--help"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "trades" not in out or "recent-trades" in out  # recent-trades still allowed
    # be strict about the removed subcommands
    assert " trades " not in out  # as a subcommand listing token
    assert "order-events" not in out
    assert "--stream" not in out
    assert "--json" in out


def test_orderbook_help_has_no_stream_or_count(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["orderbook", "--help"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "--stream" not in out
    assert "--count" not in out


def test_trades_command_is_removed(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["trades", "005930"])
    assert exc_info.value.code != 0


def test_order_events_command_is_removed(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["order-events"])
    assert exc_info.value.code != 0


# ---------- capabilities -----------------------------------------------------


def test_capabilities_default_is_plain_text(capsys):
    rc = cli_main.main(["capabilities"])
    assert rc == 0
    out = capsys.readouterr().out
    assert not out.lstrip().startswith("{")
    assert "Provider:" in out
    assert "Markets:" in out
    assert "Streams:" in out


def test_capabilities_json_mode_outputs_json(capsys):
    rc = cli_main.main(["--json", "capabilities"])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["provider"] == "kis"


# ---------- doctor -----------------------------------------------------------


def test_doctor_plain_text(monkeypatch, capsys):
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    rc = cli_main.main(["doctor"])
    # no creds -> not ready -> exit 1
    assert rc == 1
    out = capsys.readouterr().out
    assert "Provider: kis" in out
    assert "Credentials:" in out
    assert "KIS_APP_KEY" in out


def test_doctor_json_mode(monkeypatch, capsys):
    monkeypatch.setenv("KIS_APP_KEY", "x")
    monkeypatch.setenv("KIS_APP_SECRET", "y")
    rc = cli_main.main(["--json", "doctor"])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["provider"] == "kis"
    assert parsed["ready"] is True


# ---------- masking via CLI --------------------------------------------------


class _StubKISClient:
    def __init__(self, overview: AccountOverviewResponse) -> None:
        self._overview = overview

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get_account_overview(self, *, account_no, account_product_code):
        return self._overview


def _make_overview(account_id: str) -> AccountOverviewResponse:
    account = AccountSummary(
        provider=ProviderRef(provider="kis", account_id=account_id),
        account_id=account_id,
    )
    equity = AccountEquitySnapshot(
        account=account,
        as_of=datetime(2025, 4, 14, 9, 0, tzinfo=timezone.utc),
        cash=Decimal("1000"),
        total_value=Decimal("2500"),
    )
    return AccountOverviewResponse(equity=equity, positions=())


def test_balance_masks_account_in_plain_text(monkeypatch, capsys):
    monkeypatch.setenv("KIS_APP_KEY", "x")
    monkeypatch.setenv("KIS_APP_SECRET", "y")
    overview = _make_overview("12345678")
    monkeypatch.setattr(cli_main, "_build_kis_client", lambda: _StubKISClient(overview))
    rc = cli_main.main(["balance", "--account-no", "12345678"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "****5678" in out
    assert "12345678" not in out


def test_balance_json_mode_does_not_mask(monkeypatch, capsys):
    monkeypatch.setenv("KIS_APP_KEY", "x")
    monkeypatch.setenv("KIS_APP_SECRET", "y")
    overview = _make_overview("12345678")
    monkeypatch.setattr(cli_main, "_build_kis_client", lambda: _StubKISClient(overview))
    rc = cli_main.main(["--json", "balance", "--account-no", "12345678"])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    # raw JSON path must preserve the original id unmasked
    assert parsed["equity"]["account"]["account_id"] == "12345678"


# ---------- formatter unit tests --------------------------------------------


def test_mask_account_helper():
    assert cli_format._mask_account("12345678") == "****5678"
    assert cli_format._mask_account(None) == "-"
    # fewer than 4 digits -> just "****"
    assert cli_format._mask_account("9") == "****"
    assert cli_format._mask_account("ab12") == "****"


def test_render_output_quote_plain_text():
    q = QuoteResponse(
        occurred_at=datetime(2025, 4, 14, 0, 0, tzinfo=timezone.utc),
        last=Decimal("71000"),
        open=Decimal("70900"),
        high=Decimal("71400"),
        low=Decimal("70500"),
        previous_close=Decimal("70900"),
        change=Decimal("100"),
        change_rate=Decimal("0.14"),
        volume=None,
    )
    out = cli_format.render_output(q, as_json=False)
    assert "last" in out and "71000" in out
    assert "2025-04-14T00:00:00+00:00" in out
    assert "volume" in out and "volume         : -" in out  # None renders as '-'


def test_render_output_bars_plain_text():
    resp = BarsResponse(
        timeframe="day",
        adjusted=True,
        bars=(
            Bar(
                opened_at=datetime(2025, 4, 14, 0, 0, tzinfo=timezone.utc),
                timeframe="day",
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("95"),
                close=Decimal("105"),
                volume=Decimal("1000"),
            ),
        ),
    )
    out = cli_format.render_output(resp, as_json=False)
    assert "Timeframe: day" in out
    assert "Bars: 1" in out
    assert "Adjusted: yes" in out


def test_render_output_recent_trades_plain_text():
    resp = RecentTradesResponse(
        trades=(
            TradePrint(
                occurred_at=datetime(2025, 4, 14, 9, 0, tzinfo=timezone.utc),
                price=Decimal("100"),
                quantity=Decimal("10"),
                ask_price=None,
                bid_price=Decimal("99"),
            ),
        )
    )
    out = cli_format.render_output(resp, as_json=False)
    assert "Trades: 1" in out
    assert "100" in out
    assert "99" in out


def test_render_output_orderbook_plain_text():
    resp = OrderBookResponse(
        occurred_at=datetime(2025, 4, 14, 9, 0, tzinfo=timezone.utc),
        asks=(QuoteLevel(price=Decimal("101"), quantity=Decimal("5")),),
        bids=(QuoteLevel(price=Decimal("99"), quantity=Decimal("7")),),
        total_ask_quantity=Decimal("5"),
        total_bid_quantity=Decimal("7"),
    )
    out = cli_format.render_output(resp, as_json=False)
    assert "total_ask_qty" in out
    assert "101" in out and "99" in out


def test_render_output_investor_flow_plain_text():
    resp = InvestorFlowResponse(
        as_of_date=date(2025, 4, 14),
        retail=InvestorFlowBucket(net_buy_quantity=Decimal("1")),
        foreign=InvestorFlowBucket(net_buy_quantity=Decimal("2")),
        institution=InvestorFlowBucket(net_buy_quantity=Decimal("3")),
    )
    out = cli_format.render_output(resp, as_json=False)
    assert "2025-04-14" in out
    assert "net_buy_quantity" in out


def test_render_output_positions_masks_not_applicable():
    pos = PositionLot(
        instrument=InstrumentRef(symbol="005930"),
        quantity=Decimal("10"),
        average_price=Decimal("70000"),
        market_price=Decimal("71000"),
        market_value=Decimal("710000"),
        unrealized_pnl=Decimal("10000"),
        unrealized_pnl_rate=Decimal("0.014"),
    )
    resp = AccountOverviewResponse(
        equity=AccountEquitySnapshot(
            account=AccountSummary(
                provider=ProviderRef(provider="kis", account_id="99998888"),
                account_id="99998888",
            ),
            as_of=datetime(2025, 4, 14, 9, 0, tzinfo=timezone.utc),
        ),
        positions=(pos,),
    )
    out = cli_format.render_output(resp, as_json=False)
    assert "****8888" in out
    assert "99998888" not in out
    assert "005930" in out
    assert "Positions: 1" in out


def test_render_output_open_orders_masks_account():
    order = OpenOrder(
        order_ref=ProviderOrderRef(provider="kis", order_id="ORDER1", account_id="11112222"),
        instrument=InstrumentRef(symbol="005930"),
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1"),
        state=OrderLifecycleState.UNKNOWN,
    )
    resp = OpenOrdersResponse(orders=(order,))
    out = cli_format.render_output(resp, as_json=False)
    assert "****2222" in out
    assert "11112222" not in out
    assert "ORDER1" in out


def test_render_output_json_preserves_decimal_strings():
    q = QuoteResponse(
        occurred_at=datetime(2025, 4, 14, 0, 0, tzinfo=timezone.utc),
        last=Decimal("71000.12"),
    )
    out = cli_format.render_output(q, as_json=True)
    parsed = json.loads(out)
    assert parsed["last"] == "71000.12"
