"""Entry point for the wallet TUI."""
from __future__ import annotations

import argparse
import os
import sys

from .app import run_tui


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Wallet TUI - A beautiful CLI for the custodial wallet")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the wallet API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("WALLET_TUI_TOKEN"),
        help="Use existing API session token and bypass Telegram login",
    )
    args = parser.parse_args()

    try:
        run_tui(base_url=args.url, token=args.token)
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
