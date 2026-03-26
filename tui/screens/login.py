"""Login screen for TUI."""
from __future__ import annotations

import threading
import time
import webbrowser
import sys

from textual.screen import Screen
from textual.widgets import Button, Static
from textual.containers import Vertical


class LoginScreen(Screen):
    CSS = """
    LoginScreen { align: center middle; }
    #container { width: 60; height: auto; border: solid $primary; padding: 2 4; }
    #title { text-style: bold; color: $accent; text-align: center; margin-bottom: 2; }
    #subtitle { text-align: center; color: $text-muted; margin-bottom: 2; }
    #status { text-align: center; margin: 1 0; color: $accent; }
    #error { color: $error; text-align: center; margin-top: 1; }
    .hidden { display: none; }
    """

    def __init__(self):
        super().__init__()
        self.pending_token = None
        self.polling_active = False

    def compose(self):
        with Vertical(id="container"):
            yield Static("💰 Wallet TUI", id="title")
            yield Static("Test Mode", id="subtitle")
            yield Button("🔐 Login with Telegram", id="login")
            yield Static("", id="status")
            yield Static("", id="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "login":
            self._do_login()

    def _do_login(self):
        status = self.query_one("#status")
        error = self.query_one("#error")
        error.update("")
        status.update("🔄 Starting...")

        try:
            # Get bot info
            bot = self.app.api.get_bot_info()
            print(f"Bot: {bot.username}", file=sys.stderr)

            # Create pending auth
            pending = self.app.api.create_pending_auth()
            self.pending_token = pending["token"]
            print(f"Token: {self.pending_token}", file=sys.stderr)

            # Open Telegram
            url = f"https://t.me/{bot.username}?start=auth_{self.pending_token}"
            print(f"Opening: {url}", file=sys.stderr)
            webbrowser.open(url)

            status.update("✅ Opened Telegram. Complete login there...")

            # Start polling thread
            self.polling_active = True
            t = threading.Thread(target=self._poll, daemon=True)
            t.start()

        except Exception as e:
            error.update(f"Error: {e}")
            print(f"Login error: {e}", file=sys.stderr)

    def _poll(self):
        """Poll for auth completion."""
        print("Polling started", file=sys.stderr)
        for i in range(60):
            if not self.polling_active:
                print("Polling stopped", file=sys.stderr)
                return

            try:
                resp = self.app.api.check_pending_auth(self.pending_token)
                print(f"Poll {i}: {resp}", file=sys.stderr)

                data = resp.get("data", {})
                if data.get("status") == "completed":
                    token = data.get("session_token")
                    user_id = data.get("telegram_user_id")
                    print(f"Auth completed! Token: {token[:20]}...", file=sys.stderr)
                    self.app.call_next(self.app.on_telegram_login_success, {
                        "session_token": token,
                        "user_id": user_id,
                    })
                    return

            except Exception as e:
                print(f"Poll error: {e}", file=sys.stderr)

            time.sleep(1)

        print("Polling timed out", file=sys.stderr)
        self.polling_active = False
