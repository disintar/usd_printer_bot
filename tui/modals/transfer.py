"""Transfer modal."""
from __future__ import annotations

from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static
from textual.containers import Horizontal, Vertical


class TransferModal(ModalScreen):
    """Modal for transferring funds."""

    CSS = """
    TransferModal {
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
        with Vertical(id="modal-container"):
            yield Static("💸 Transfer Funds", id="title")
            yield Input(placeholder="Recipient Telegram User ID", id="recipient", type="number")
            yield Input(placeholder="Amount (USDt)", id="amount", type="number")
            yield Horizontal(Button("Transfer", id="submit", variant="primary"))
            yield Horizontal(Button("Cancel", id="cancel"))
            yield Static("", id="result")

    def on_mount(self) -> None:
        self.query_one("#recipient").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "submit":
            self._transfer()

    def _transfer(self) -> None:
        recipient = self.query_one("#recipient").value.strip()
        amount = self.query_one("#amount").value.strip()
        result = self.query_one("#result")

        if not recipient or not amount:
            result.update("[red]Please fill all fields[/red]")
            return

        try:
            self.app.api.transfer(int(recipient), amount)
            self.app.pop_screen()
            self.app.refresh_screens()
        except Exception as e:
            result.update(f"[red]Error: {e}[/red]")
