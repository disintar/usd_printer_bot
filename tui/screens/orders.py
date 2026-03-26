"""Orders screen."""
from __future__ import annotations

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ..utils import format_decimal


class OrdersScreen(Screen):
    """Screen showing order history."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    CSS = """
    OrdersScreen {
        layout: vertical;
    }
    #title {
        text-style: bold;
        color: $accent;
        text-align: center;
        margin: 1 0;
    }
    #orders-table {
        height: 16;
    }
    #order-detail {
        margin-top: 1;
        border: solid $primary;
        min-height: 4;
        padding: 1;
    }
    """

    def compose(self):
        with Vertical():
            yield Static("📋 Order History", id="title")
            yield DataTable(id="orders-table")
            yield Static("Select an order row to view details", id="order-detail")

    def on_mount(self) -> None:
        table = self.query_one("#orders-table", DataTable)
        table.add_columns("ID", "Side", "Asset", "Qty", "Price", "Notional", "Status", "Created")
        self._load_orders()

    def action_refresh(self) -> None:
        self._load_orders()

    def _load_orders(self) -> None:
        table = self.query_one("#orders-table", DataTable)
        table.clear()

        try:
            orders = self.app.api.get_orders()
            for order in orders:
                side_color = "[green]BUY[/green]" if order["side"] == "buy" else "[red]SELL[/red]"
                table.add_row(
                    str(order["order_id"]),
                    side_color,
                    order["asset_id"],
                    format_decimal(order["quantity"], 4),
                    f"${format_decimal(order['price'])}",
                    f"${format_decimal(order['notional'])}",
                    order["status"].upper(),
                    order["created_at"][:19],
                )
        except Exception:
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = event.control
        if not isinstance(table, DataTable):
            return
        if table.id != "orders-table":
            return
        row = None
        row_key = getattr(event, "row_key", None)
        if row_key is not None:
            row = table.get_row(row_key)
        else:
            row_index = int(getattr(event, "cursor_row", 0))
            if table.row_count > 0 and row_index < table.row_count:
                row = table.get_row_at(row_index)
        if not row:
            return
        detail = self.query_one("#order-detail", Static)
        try:
            order_id = int(str(row[0]))
            order = self.app.api.get_order(order_id)
            detail.update(
                " | ".join(
                    [
                        f"Order #{order['order_id']}",
                        f"{order['side'].upper()} {order['asset_id']}",
                        f"qty={order['quantity']}",
                        f"price=${order['price']}",
                        f"notional=${order['notional']}",
                        f"status={order['status']}",
                    ]
                )
            )
        except Exception as e:
            detail.update(f"[red]Order detail error: {e}[/red]")
