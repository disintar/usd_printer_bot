"""Portfolio screen."""
from __future__ import annotations

from decimal import Decimal

from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ..utils import format_decimal


class PortfolioScreen(Screen):
    """Portfolio overview screen."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    CSS = """
    PortfolioScreen {
        layout: vertical;
    }
    #title {
        text-style: bold;
        color: $accent;
        text-align: center;
        margin: 1 0;
    }
    .portfolio-stats {
        layout: horizontal;
        height: auto;
    }
    .stat {
        width: 1fr;
        border: solid $primary;
        padding: 1;
        align: center middle;
    }
    #portfolio-table {
        height: 15;
        margin-top: 1;
    }
    """

    def compose(self):
        yield Static("📊 Portfolio", id="title")
        yield Container(id="stats-container")
        yield DataTable(id="portfolio-table")

    def on_mount(self) -> None:
        self._load_portfolio()

    def action_refresh(self) -> None:
        self._load_portfolio()

    def _load_portfolio(self) -> None:
        try:
            portfolio = self.app.api.get_portfolio()
            risk = self.app.api.get_risk()

            stats_container = self.query_one("#stats-container", Container)
            stats_container.remove_children()

            total = Decimal(portfolio["total_balance_usdt"])
            pnl_abs = Decimal(portfolio["pnl_absolute"])
            pnl_pct = Decimal(portfolio["pnl_percent"])
            risk_score = risk["risk_score"]
            color = "pnl-positive" if pnl_abs >= 0 else "pnl-negative"
            stats_row = Horizontal(
                Vertical(
                    Static("Total Balance"),
                    Static(f"${format_decimal(total)}", classes="balance-value"),
                    classes="stat",
                ),
                Vertical(
                    Static("PnL"),
                    Static(
                        f"${format_decimal(pnl_abs)} ({format_decimal(pnl_pct)}%)",
                        classes=f"balance-value {color}",
                    ),
                    classes="stat",
                ),
                Vertical(
                    Static("Risk Score"),
                    Static(f"{risk_score}/100", classes="balance-value"),
                    classes="stat",
                ),
                Vertical(
                    Static("Assets"),
                    Static(str(len(portfolio.get("assets", []))), classes="balance-value"),
                    classes="stat",
                ),
                classes="portfolio-stats",
            )
            stats_container.mount(stats_row)

            table = self.query_one("#portfolio-table", DataTable)
            table.clear()
            table.add_columns("Asset", "Quantity", "Value (USDt)", "Allocation %")

            for asset in portfolio.get("assets", []):
                alloc = Decimal(asset["allocation_percent"])
                table.add_row(
                    asset["asset_id"],
                    format_decimal(asset["quantity"], 4),
                    f"${format_decimal(asset['value_usdt'])}",
                    f"{format_decimal(alloc)}%",
                )

        except Exception:
            pass
