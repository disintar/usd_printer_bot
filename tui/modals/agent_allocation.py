"""Agent allocation modal."""
from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class AgentAllocationModal(ModalScreen):
    """Modal for updating agent allocation percentages."""

    AGENTS = ("Buy", "Cover", "Sell", "Short", "Hold")

    CSS = """
    AgentAllocationModal {
        align: center middle;
    }
    #modal-container {
        width: 68;
        height: auto;
        border: solid $accent;
        padding: 2 4;
        background: $surface;
    }
    .row {
        margin: 0 0 1 0;
        height: auto;
    }
    .agent-label {
        width: 12;
    }
    .agent-input {
        width: 14;
    }
    #result {
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.inputs: dict[str, Input] = {}

    def compose(self):
        with Vertical(id="modal-container"):
            yield Static("⚖️ Agent Allocation", id="title")
            yield Static("Set percentages; total must be 100")
            for agent in self.AGENTS:
                with Horizontal(classes="row"):
                    yield Label(f"{agent}:", classes="agent-label")
                    inp = Input(placeholder="0-100", id=f"alloc-{agent}", classes="agent-input")
                    self.inputs[agent] = inp
                    yield inp
            with Horizontal(classes="row"):
                yield Button("Save", id="save", variant="primary")
                yield Button("Cancel", id="cancel")
            yield Static("", id="result")

    def on_mount(self) -> None:
        try:
            allocation = self.app.api.get_allocation().get("allocation", {})
            for agent, input_widget in self.inputs.items():
                value = allocation.get(agent)
                if value is not None:
                    input_widget.value = str(value)
        except Exception:
            pass
        self.inputs[self.AGENTS[0]].focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.pop_screen()
            return
        if event.button.id == "save":
            self._save()

    def _save(self) -> None:
        result = self.query_one("#result", Static)
        allocation: dict[str, float] = {}

        try:
            for agent, input_widget in self.inputs.items():
                allocation[agent] = float(input_widget.value.strip() or "0")
            total = sum(allocation.values())
            if abs(total - 100.0) > 1e-6:
                result.update(f"[red]Allocation must sum to 100 (current {total:.2f})[/red]")
                return

            self.app.api.update_allocation(allocation)
            self.app.pop_screen()
            self.app.refresh_screens()
        except Exception as e:
            result.update(f"[red]Error: {e}[/red]")
