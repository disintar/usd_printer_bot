"""Deposit/Withdraw modal."""
from __future__ import annotations

from typing import Any

from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static
from textual.containers import Horizontal, Vertical


class DepositWithdrawModal(ModalScreen):
    """Modal for deposit/withdraw."""

    def __init__(self, action: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.action = action

    CSS = """
    DepositWithdrawModal {
        align: center middle;
    }
    #modal-container {
        width: 50;
        height: auto;
        border: solid $accent;
        padding: 2 4;
        background: $surface;
    }
    Input {
        margin: 1 0;
    }
    #result {
        margin-top: 1;
        text-align: center;
    }
    """

    def compose(self):
        icon = "⬇️" if self.action == "deposit" else "⬆️"
        label = "Deposit" if self.action == "deposit" else "Withdraw"
        variant = "success" if self.action == "deposit" else "warning"
        with Vertical(id="modal-container"):
            yield Static(f"{icon} {label} Funds", id="title")
            yield Input(placeholder="Amount (USDt)", id="amount", type="number")
            yield Horizontal(Button(label, id="submit", variant=variant))
            yield Horizontal(Button("Cancel", id="cancel"))
            yield Static("", id="result")

    def on_mount(self) -> None:
        self.query_one("#amount").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "submit":
            self._action()

    def _action(self) -> None:
        amount = self.query_one("#amount").value.strip()
        result = self.query_one("#result")

        if not amount:
            result.update("[red]Please enter amount[/red]")
            return

        try:
            if self.action == "deposit":
                self.app.api.deposit(amount)
            else:
                self.app.api.withdraw(amount)
            self.app.pop_screen()
            self.app.refresh_screens()
        except Exception as e:
            result.update(f"[red]Error: {e}[/red]")
