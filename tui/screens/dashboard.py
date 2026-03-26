"""Main dashboard screen."""
from __future__ import annotations
from decimal import Decimal

from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import DataTable, Static

from ..api import UnauthorizedError
from ..modals.order import OrderModal
from ..utils import format_decimal, mark_colored
from .dashboard_analytics import DashboardAnalyticsService
class MainScreen(Screen):
    """Main wallet dashboard."""

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("b", "buy", "Buy", show=True),
        Binding("s", "sell", "Sell", show=True),
        Binding("d", "deposit", "Deposit", show=True),
        Binding("w", "withdraw", "Withdraw", show=True),
        Binding("t", "transfer", "Transfer", show=True),
        Binding("enter", "generate_analytics", "Analyze", show=True),
        Binding("o", "orders", "Orders", show=True),
        Binding("p", "portfolio", "Portfolio", show=True),
    ]

    CSS = """
    MainScreen {
        layout: vertical;
        width: 100%;
        padding: 1 2;
        background: $surface-darken-2;
    }
    #main-panel {
        width: 100%;
        padding: 1 2;
        border: double $accent;
        background: $surface;
    }
    .section-title {
        text-style: bold;
        color: $accent;
        margin: 1 0;
    }
    #key-help {
        color: $warning-lighten-2;
        margin-bottom: 0;
    }
    #account-info {
        margin: 1 0 0 0;
        color: $text;
    }
    #tables-row {
        width: 100%;
        height: auto;
        margin-top: 1;
    }
    .table-pane {
        width: 1fr;
        margin-right: 1;
    }
    .balance-label {
        color: $text-muted;
        text-style: bold;
    }
    .balance-value {
        text-style: bold;
    }
    .stat-card {
        width: 100%;
        height: auto;
        border: tall $primary-lighten-1;
        padding: 1 1;
        margin: 0 0 1 0;
        background: $surface-darken-1;
    }
    #positions-table {
        height: 10;
        margin-top: 1;
        border: heavy $primary;
    }
    #assets-table {
        height: 10;
        margin-top: 1;
        border: heavy $secondary;
    }
    #asset-detail {
        border: heavy $accent;
        padding: 1;
        min-height: 7;
        max-height: 9;
        background: $surface-darken-1;
    }
    #analytics-help {
        color: $warning-lighten-2;
        margin-top: 1;
    }
    #analytics-table {
        height: 8;
        border: heavy $accent;
        background: $surface-darken-1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.selected_asset: str | None = None
        self._live_refresh_timer: Timer | None = None

    def compose(self):
        with Vertical(id="main-panel"):
            yield Static("XENAGE TEST TRADER", classes="section-title")
            yield Static(
                "Keys: q quit | r refresh | b buy | s sell | d deposit | w withdraw | "
                "t transfer | Enter analyze ticker | o orders | p portfolio",
                id="key-help",
            )
            yield Container(id="balance-grid")
            yield Static("", id="account-info")
            with Horizontal(id="tables-row"):
                with Vertical(classes="table-pane"):
                    yield Static("📊 Positions", classes="section-title")
                    yield DataTable(id="positions-table")
                with Vertical(classes="table-pane"):
                    yield Static("📈 Assets", classes="section-title")
                    yield DataTable(id="assets-table")
            yield Static("🔍 Asset Detail & Analytics", classes="section-title")
            yield Container(id="asset-detail")
            yield Static(
                "Analytics: pick a tradeable ticker in Positions/Assets, Enter refreshes advisers + agent view.",
                id="analytics-help",
            )
            yield DataTable(id="analytics-table")

    def on_mount(self) -> None:
        self._setup_tables()
        self.refresh_data()
        self._live_refresh_timer = self.set_interval(1.0, self.refresh_data)

    def on_unmount(self) -> None:
        if self._live_refresh_timer is not None:
            self._live_refresh_timer.stop()
            self._live_refresh_timer = None

    def _setup_tables(self) -> None:
        positions_table = self.query_one("#positions-table", DataTable)
        positions_table.add_columns("Asset", "Qty", "Value", "PnL %", "Mark", "Thought")
        assets_table = self.query_one("#assets-table", DataTable)
        assets_table.add_columns("Asset", "Price", "Balance", "Value", "Mark")
        analytics_table = self.query_one("#analytics-table", DataTable)
        analytics_table.add_columns("Source", "Thought")
        positions_table.cursor_type = "row"
        assets_table.cursor_type = "row"

    def action_refresh(self) -> None:
        self.refresh_data()

    def action_quit(self) -> None:
        self.app.exit()

    def action_buy(self) -> None:
        asset_id = self._get_trade_asset_id()
        if asset_id:
            self.app.push_screen(OrderModal("buy", asset_id=asset_id))
            return
        self.app.push_screen("order_buy")

    def action_sell(self) -> None:
        asset_id = self._get_trade_asset_id()
        if asset_id:
            self.app.push_screen(OrderModal("sell", asset_id=asset_id))
            return
        self.app.push_screen("order_sell")

    def action_deposit(self) -> None:
        self.app.push_screen("deposit")

    def action_withdraw(self) -> None:
        self.app.push_screen("withdraw")

    def action_transfer(self) -> None:
        self.app.push_screen("transfer")

    def action_orders(self) -> None:
        self.app.push_screen("orders")

    def action_portfolio(self) -> None:
        self.app.push_screen("portfolio")

    def action_generate_analytics(self) -> None:
        asset_id = self._get_trade_asset_id()
        if not asset_id:
            return
        if asset_id == "USDt":
            asset_id = self._table_cursor_asset("positions-table") or self.selected_asset
        if not asset_id or asset_id == "USDt":
            self._update_analytics_table("USDt")
            return
        self.selected_asset = asset_id
        self._update_asset_detail(asset_id)
        self._show_loading_recommendation(asset_id)
        self.set_timer(0.01, lambda: self._update_analytics_table(asset_id))

    def _table_cursor_asset(self, table_id: str) -> str | None:
        table = self.query_one(f"#{table_id}", DataTable)
        if table.row_count == 0:
            return None
        row_index = table.cursor_row if table.cursor_row < table.row_count else 0
        return str(table.get_row_at(row_index)[0])

    def _get_trade_asset_id(self) -> str | None:
        positions_table = self.query_one("#positions-table", DataTable)
        assets_table = self.query_one("#assets-table", DataTable)
        focused_widget = self.app.focused
        if focused_widget is positions_table:
            return self._table_cursor_asset("positions-table")
        if focused_widget is assets_table:
            return self._table_cursor_asset("assets-table")
        if self.selected_asset:
            return self.selected_asset
        return self._table_cursor_asset("assets-table") or self._table_cursor_asset("positions-table")

    def refresh_data(self) -> None:
        token = str(getattr(self.app.api.config, "token", "") or "").strip()
        if not token:
            return
        try:
            self._update_balance()
            self._update_account_info()
            self._update_positions()
            self._update_assets()
            if self.selected_asset:
                self._update_asset_detail(self.selected_asset)
        except UnauthorizedError:
            self.app.handle_unauthorized()
        except Exception:
            pass

    def _update_balance(self) -> None:
        balance = self.app.api.get_balance()
        grid = self.query_one("#balance-grid", Container)
        grid.remove_children()
        cash = Decimal(balance["cash_usdt"])
        equity = Decimal(balance["equity_usdt"])
        total = Decimal(balance["total_balance_usdt"])
        pnl_abs = Decimal(balance["pnl_absolute"])
        pnl_pct = Decimal(balance["pnl_percent"])
        pnl_sign = "+" if pnl_abs >= 0 else ""
        stats = [
            ("Cash", f"${format_decimal(cash)}"),
            ("Equity", f"${format_decimal(equity)}"),
            ("Total", f"${format_decimal(total)}"),
            (f"PnL ({pnl_sign}{format_decimal(pnl_pct)}%)", f"{pnl_sign}${format_decimal(pnl_abs)}"),
        ]
        for label, value in stats:
            card = Vertical(classes="stat-card")
            grid.mount(card)
            card.mount(
                Static(label, classes="balance-label"),
                Static(value, classes="balance-value"),
            )

    def _update_account_info(self) -> None:
        info = self.query_one("#account-info", Static)
        try:
            address = self.app.api.get_address()["address"]
            prices = self.app.api.get_prices()
            clock = self.app.api.get_time()
            top_symbols = ["AAPLx", "NVDAx", "TSLAx", "COINx"]
            top_prices = " | ".join(f"{sym}: ${format_decimal(prices[sym])}" for sym in top_symbols if sym in prices)
            server_time = str(clock.get("server_time_utc", "n/a"))
            simulated_time = str(clock.get("simulated_time_utc", "n/a"))
            speed = f"{clock.get('hours_per_tick', 1)}h / sec"
            info.update(
                f"Address: {address} | Server: {server_time} | Simulated: {simulated_time} ({speed}) | Prices: {top_prices}"
            )
        except Exception as e:
            info.update(f"[yellow]Info unavailable: {e}[/yellow]")

    def _update_positions(self) -> None:
        table = self.query_one("#positions-table", DataTable)
        previous_row = table.cursor_row
        previous_col = table.cursor_column
        previous_asset_id: str | None = None
        if table.row_count > 0 and previous_row < table.row_count:
            previous_asset_id = str(table.get_row_at(previous_row)[0])
        table.clear()

        try:
            positions = self.app.api.get_positions()
            for pos in positions:
                pnl_pct = Decimal(pos["pnl_percent"])
                pnl_str = f"+{format_decimal(pnl_pct)}%" if pnl_pct >= 0 else f"{format_decimal(pnl_pct)}%"
                mark = mark_colored(pos["mark"])
                thought = str(pos.get("advisor_thought", ""))

                table.add_row(
                    pos["asset_id"],
                    format_decimal(pos["quantity"], 4),
                    f"${format_decimal(pos['net_worth'])}",
                    pnl_str,
                    mark,
                    thought,
                    key=pos["asset_id"],
                )
            if previous_asset_id:
                position_ids = {str(pos["asset_id"]) for pos in positions}
                if previous_asset_id in position_ids:
                    row_index = table.get_row_index(previous_asset_id)
                    table.move_cursor(row=row_index, column=previous_col, animate=False, scroll=False)
        except Exception:
            pass

    def _update_assets(self) -> None:
        table = self.query_one("#assets-table", DataTable)
        previous_row = table.cursor_row
        previous_col = table.cursor_column
        previous_asset_id: str | None = None
        if table.row_count > 0 and previous_row < table.row_count:
            previous_asset_id = str(table.get_row_at(previous_row)[0])
        table.clear()

        try:
            assets = self.app.api.get_assets()
            for asset in assets:
                mark = mark_colored(asset["mark"])
                table.add_row(
                    asset["asset_id"],
                    f"${format_decimal(asset['current_price'])}",
                    format_decimal(asset["balance"], 4),
                    f"${format_decimal(asset['net_worth'])}",
                    mark,
                    key=asset["asset_id"],
                )
            if previous_asset_id:
                asset_ids = {str(asset["asset_id"]) for asset in assets}
                if previous_asset_id in asset_ids:
                    row_index = table.get_row_index(previous_asset_id)
                    table.move_cursor(row=row_index, column=previous_col, animate=False, scroll=False)
            if not self.selected_asset and assets:
                self.selected_asset = str(assets[0]["asset_id"])
        except Exception:
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = event.control
        if not isinstance(table, DataTable):
            return
        table_id = table.id
        if table_id in {"assets-table", "positions-table"}:
            row = None
            row_key = getattr(event, "row_key", None)
            if row_key is not None:
                row = table.get_row(row_key)
            else:
                row_index = int(getattr(event, "cursor_row", 0))
                if table.row_count > 0 and row_index < table.row_count:
                    row = table.get_row_at(row_index)
            if row:
                self.selected_asset = row[0]
                self._update_asset_detail(row[0])

    def _show_loading_recommendation(self, asset_id: str) -> None:
        table = self.query_one("#analytics-table", DataTable)
        table.clear()
        table.add_row("System", f"Loading recommendation for {asset_id}...")

    def _update_asset_detail(self, asset_id: str) -> None:
        detail_container = self.query_one("#asset-detail", Container)
        detail_container.remove_children()

        try:
            asset = self.app.api.get_asset(asset_id)
            pnl_pct = Decimal(asset["pnl_percent"])
            pnl_abs = Decimal(asset["pnl_absolute"])
            pnl_tag = "green" if pnl_abs >= 0 else "red"
            pnl_sign = "+" if pnl_abs >= 0 else ""

            for text in [
                f"[bold]{asset_id}[/bold] @ ${format_decimal(asset['current_price'])}",
                f"Balance: {format_decimal(asset['balance'], 4)} {asset_id}",
                f"Net Worth: ${format_decimal(asset['net_worth'])}",
                f"PnL: [{pnl_tag}]{pnl_sign}{format_decimal(pnl_abs)} ({pnl_sign}{format_decimal(pnl_pct)}%)[/]",
                f"Mark: {mark_colored(asset['mark'])}",
                f"Advisor Thought: {asset.get('advisor_thought', '')}",
                "",
                "Adviser recommendation is available in the analytics table below.",
            ]:
                detail_container.mount(Static(text))

        except Exception as e:
            detail_container.mount(Static(f"[red]Error: {e}[/red]"))

    def _update_analytics_table(self, asset_id: str) -> None:
        table = self.query_one("#analytics-table", DataTable)
        DashboardAnalyticsService.populate(table, self.app.api, asset_id)
