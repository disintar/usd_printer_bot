"""Real-process integration test for backend + time-warp cron + TUI session token flow."""
from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
from decimal import Decimal

import httpx
import pytest

from tui.app import WalletTUI
from tui.modals.deposit_withdraw import DepositWithdrawModal
from tui.modals.order import OrderModal
from tui.screens.dashboard import MainScreen


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_health(base_url: str, timeout_seconds: float = 30.0) -> None:
    started = time.time()
    while (time.time() - started) < timeout_seconds:
        try:
            response = httpx.get(f"{base_url}/health", timeout=1.0)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    raise RuntimeError("Backend health endpoint is not ready")


def _auth_session_token(base_url: str, telegram_user_id: int) -> str:
    create = httpx.post(f"{base_url}/auth/pending", json={}, timeout=10.0)
    create.raise_for_status()
    pending_token = create.json()["data"]["token"]

    complete = httpx.post(
        f"{base_url}/auth/complete",
        json={"token": pending_token, "telegram_user_id": telegram_user_id},
        timeout=10.0,
    )
    complete.raise_for_status()
    return str(complete.json()["data"]["session_token"])


@pytest.mark.skipif(
    os.getenv("RUN_REAL_TUI_INTEGRATION") != "1",
    reason="Set RUN_REAL_TUI_INTEGRATION=1 to run real-process integration",
)
def test_real_session_token_flow_with_live_time_and_buttons() -> None:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["FMP_ENABLED"] = "false"
    env["PRICE_CRON_ENABLED"] = "false"
    env["TEST_TIME_WARP_ENABLED"] = "true"
    env["TEST_TIME_WARP_INTERVAL_SECONDS"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    cron = subprocess.Popen(
        [sys.executable, "manage.py", "run_price_cron", "--interval-seconds", "1", "--test-time-warp"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_health(base_url)
        session_token = _auth_session_token(base_url, telegram_user_id=991337)

        async def _run() -> None:
            app = WalletTUI(base_url=base_url, initial_token=session_token)
            async with app.run_test() as pilot:
                await pilot.pause()
                assert isinstance(app.screen, MainScreen)

                initial_cash = Decimal(app.api.get_balance()["cash_usdt"])
                initial_time = app.api.get_time()["simulated_time_utc"]
                initial_price = Decimal(app.api.get_prices()["AAPLx"])

                await pilot.click("#btn-deposit")
                await pilot.pause()
                assert isinstance(app.screen, DepositWithdrawModal)
                app.screen.query_one("#amount").value = "200"
                await pilot.click("#submit")
                await pilot.pause()
                after_deposit_cash = Decimal(app.api.get_balance()["cash_usdt"])
                assert after_deposit_cash == initial_cash + Decimal("200.00")

                await pilot.click("#btn-buy")
                await pilot.pause()
                assert isinstance(app.screen, OrderModal)
                app.screen.query_one("#asset_id").value = "AAPLx"
                app.screen.query_one("#quantity").value = "0.4"
                await pilot.click("#submit")
                await pilot.pause()

                pnl_before = Decimal(app.api.get_balance()["pnl_absolute"])
                await asyncio.sleep(2.2)
                await pilot.pause()
                time_after = app.api.get_time()["simulated_time_utc"]
                price_after = Decimal(app.api.get_prices()["AAPLx"])
                pnl_after = Decimal(app.api.get_balance()["pnl_absolute"])
                assert time_after != initial_time
                assert price_after != initial_price
                assert pnl_after != pnl_before

                await pilot.click("#btn-sell")
                await pilot.pause()
                assert isinstance(app.screen, OrderModal)
                app.screen.query_one("#asset_id").value = "AAPLx"
                app.screen.query_one("#quantity").value = "0.1"
                await pilot.click("#submit")
                await pilot.pause()

                before_withdraw = Decimal(app.api.get_balance()["cash_usdt"])
                await pilot.click("#btn-withdraw")
                await pilot.pause()
                assert isinstance(app.screen, DepositWithdrawModal)
                app.screen.query_one("#amount").value = "50"
                await pilot.click("#submit")
                await pilot.pause()
                after_withdraw = Decimal(app.api.get_balance()["cash_usdt"])
                assert after_withdraw == before_withdraw - Decimal("50.00")

        asyncio.run(_run())
    finally:
        for proc in (cron, server):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
