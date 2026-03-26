"""Session token persistence for TUI."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile


@dataclass
class SessionTokenStore:
    """Persist and load wallet TUI session token from a temp file."""

    token_file_path: Path | None = None

    def resolve_path(self) -> Path:
        """Get the token file path."""
        if self.token_file_path is not None:
            return self.token_file_path
        temp_dir = Path(tempfile.gettempdir())
        return temp_dir / "wallet_tui_session_token"

    def load_token(self) -> str | None:
        """Load token from file if available."""
        token_path = self.resolve_path()
        if not token_path.exists():
            return None
        try:
            token = token_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not token:
            return None
        return token

    def save_token(self, token: str) -> None:
        """Save token to file."""
        token_path = self.resolve_path()
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(token.strip(), encoding="utf-8")

    def clear_token(self) -> None:
        """Remove persisted token file."""
        token_path = self.resolve_path()
        if token_path.exists():
            token_path.unlink()
