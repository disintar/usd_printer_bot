"""Rebalance screen."""
from __future__ import annotations

from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import RichLog, Static


class RebalanceScreen(Screen):
    """Rebalance recommendations screen."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
    ]

    CSS = """
    RebalanceScreen {
        layout: vertical;
    }
    #title {
        text-style: bold;
        color: $accent;
        text-align: center;
        margin: 1 0;
    }
    #actions-list {
        height: 20;
        border: solid $primary;
        padding: 1;
    }
    """

    def compose(self):
        yield Static("⚖️ Rebalance Actions", id="title")
        yield RichLog(id="actions-list")

    def on_mount(self) -> None:
        self._load_actions()

    def _load_actions(self) -> None:
        log = self.query_one("#actions-list", RichLog)

        try:
            actions = self.app.api.rebalance()
            if not actions.get("actions"):
                log.write("[yellow]Portfolio is balanced - no actions needed[/yellow]")
                return

            for action in actions["actions"]:
                act = action.get("action", "").upper()
                asset = action.get("asset_id", "")
                reason = action.get("reason", "")

                color = "green" if act == "BUY" else "red"
                log.write(f"[{color}]{act}[/{color}] {asset}: {reason}")

        except Exception as e:
            log.write(f"[red]Error: {e}[/red]")
