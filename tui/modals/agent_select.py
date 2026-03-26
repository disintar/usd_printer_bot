"""Agent selection modal."""
from __future__ import annotations

from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static, Switch
from textual.containers import Horizontal, Vertical


class AgentSelectModal(ModalScreen):
    """Modal for selecting agents."""

    CSS = """
    AgentSelectModal {
        align: center middle;
    }
    #modal-container {
        width: 60;
        height: auto;
        border: solid $accent;
        padding: 2 4;
        background: $surface;
    }
    .agent-row {
        height: 3;
        align: center middle;
    }
    #result {
        margin-top: 1;
        text-align: center;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.switches: dict[str, Switch] = {}

    def compose(self):
        agents = ["Buy", "Cover", "Sell", "Short", "Hold"]
        with Vertical(id="modal-container"):
            yield Static("🤖 Select AI Agents", id="title")
            for agent in agents:
                with Horizontal(classes="agent-row"):
                    yield Label(f"{agent}:")
                    switch = Switch(id=f"switch-{agent}", value=True)
                    self.switches[agent] = switch
                    yield switch
            yield Horizontal(
                Button("Save", id="save", variant="primary"),
                Button("Cancel", id="cancel"),
            )
            yield Static("", id="result")

    def on_mount(self) -> None:
        try:
            agents_data = self.app.api.get_agents()
            selected = agents_data.get("selected_agents", ["Buy", "Cover", "Sell", "Short", "Hold"])
            for agent, switch in self.switches.items():
                switch.value = agent in selected
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "save":
            self._save()

    def _save(self) -> None:
        selected = [agent for agent, switch in self.switches.items() if switch.value]
        result = self.query_one("#result")

        if not selected:
            result.update("[red]Select at least one agent[/red]")
            return

        try:
            self.app.api.select_agents(selected)
            self.app.pop_screen()
            self.app.refresh_screens()
        except Exception as e:
            result.update(f"[red]Error: {e}[/red]")
