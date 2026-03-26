from __future__ import annotations

import os
from pathlib import Path


class EnvFileLoader:
    """Lightweight .env loader for local development and CLI runs."""

    @classmethod
    def load_env_file(cls, env_path: Path) -> dict[str, str]:
        if not env_path.exists() or not env_path.is_file():
            return {}

        loaded: dict[str, str] = {}
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            parsed = cls._parse_line(raw_line)
            if parsed is None:
                continue
            key, value = parsed
            if key in os.environ:
                continue
            os.environ[key] = value
            loaded[key] = value
        return loaded

    @staticmethod
    def _parse_line(raw_line: str) -> tuple[str, str] | None:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            return None
        if line.startswith("export "):
            line = line[7:].strip()

        key, sep, raw_value = line.partition("=")
        if sep != "=":
            return None

        normalized_key = key.strip()
        if not normalized_key:
            return None
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return normalized_key, value
