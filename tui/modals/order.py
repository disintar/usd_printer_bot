"""Order modal for buy/sell."""
from __future__ import annotations

from typing import Any

from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static
from textual.containers import Horizontal, Vertical


class OrderModal(ModalScreen):
    """Modal for placing orders."""

    def __init__(self, order_type: str, asset_id: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.order_type = order_type
        self.asset_id = asset_id

    CSS = """
    OrderModal {
        align: center middle;
    }
    #modal-container {
        width: 50;
        height: auto;
        border: solid $accent;
        padding: 2 4;
        background: $surface;
    }
    .button-row {
        height: auto;
        margin-top: 2;
    }
    #result {
        margin-top: 1;
        text-align: center;
    }
    """

    def compose(self):
        action = "Buy" if self.order_type == "buy" else "Sell"
        variant = "success" if self.order_type == "buy" else "warning"
        with Vertical(id="modal-container"):
            yield Static(f"📈 {action} Asset", id="title")
            yield Static("Supported: TSLAx, HOODx, AMZNx, NVDAx, COINx, GOOGLx, AAPLx, MSTRx")
            yield Input(self.asset_id, placeholder="Asset ID (e.g. AAPLx)", id="asset_id")
            yield Input(placeholder="Quantity", id="quantity", type="number")
            yield Horizontal(
                Button("Place Order", id="submit", variant=variant),
                Button("Cancel", id="cancel", variant="default"),
                classes="button-row",
            )
            yield Static("", id="result")

    def on_mount(self) -> None:
        if self.asset_id:
            self.query_one("#asset_id").disabled = True
            self.query_one("#quantity").focus()
        else:
            self.query_one("#asset_id").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "submit":
            self._place_order()

    def _place_order(self) -> None:
        asset_id = self.query_one("#asset_id").value.strip()
        quantity = self.query_one("#quantity").value.strip()
        result = self.query_one("#result")

        if not asset_id or not quantity:
            result.update("[red]Please fill all fields[/red]")
            return

        try:
            if self.order_type == "buy":
                self.app.api.buy(asset_id, quantity)
            else:
                self.app.api.sell(asset_id, quantity)
            self.app.pop_screen()
            self.app.refresh_screens()
        except Exception as e:
            result.update(f"[red]Error: {e}[/red]")
