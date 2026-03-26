from __future__ import annotations

import os
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from config.env_file import EnvFileLoader


class EnvFileLoaderTests(SimpleTestCase):
    def test_load_env_file_sets_missing_values_and_preserves_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# comment",
                        "NEW_KEY=abc123",
                        "export QUOTED_KEY='hello world'",
                        "EXISTING_KEY=from_file",
                    ]
                ),
                encoding="utf-8",
            )

            os.environ["EXISTING_KEY"] = "from_env"
            loaded = EnvFileLoader.load_env_file(env_path)

            self.assertEqual(loaded["NEW_KEY"], "abc123")
            self.assertEqual(loaded["QUOTED_KEY"], "hello world")
            self.assertNotIn("EXISTING_KEY", loaded)
            self.assertEqual(os.environ["EXISTING_KEY"], "from_env")
            self.assertEqual(os.environ["NEW_KEY"], "abc123")

            del os.environ["EXISTING_KEY"]
            del os.environ["NEW_KEY"]
            del os.environ["QUOTED_KEY"]

    def test_parse_line_ignores_invalid_and_comment_lines(self) -> None:
        self.assertIsNone(EnvFileLoader._parse_line(""))
        self.assertIsNone(EnvFileLoader._parse_line("   # test"))
        self.assertIsNone(EnvFileLoader._parse_line("NO_EQUALS"))
        self.assertEqual(EnvFileLoader._parse_line("A=1"), ("A", "1"))
