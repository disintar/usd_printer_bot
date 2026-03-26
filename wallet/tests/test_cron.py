from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from wallet.models import TelegramIdentity, WalletAccount
from wallet.services.cron_jobs import CronJobsService


class CronJobsTests(TestCase):
    def test_sync_prices_and_recalculate_pnl_processes_all_users(self) -> None:
        identity1 = TelegramIdentity.objects.create(telegram_user_id=10001, token="tok1")
        identity2 = TelegramIdentity.objects.create(telegram_user_id=10002, token="tok2")
        WalletAccount.objects.create(identity=identity1)
        WalletAccount.objects.create(identity=identity2)

        with patch("wallet.services.prices.PricesService.sync_latest_prices") as mock_sync:
            result = CronJobsService.sync_prices_and_recalculate_pnl()

        mock_sync.assert_called_once_with(force=True)
        self.assertEqual(result.users_processed, 2)
        self.assertGreater(result.total_equity_usdt, Decimal("0"))

    def test_run_test_time_warp_cycle_recalculates_users(self) -> None:
        identity = TelegramIdentity.objects.create(telegram_user_id=11111, token="tok11111")
        WalletAccount.objects.create(identity=identity)

        with patch("wallet.services.cron_jobs.TestTimeWarpService.advance_and_sync_prices") as mock_tick:
            mock_tick.return_value = type(
                "TickResult",
                (),
                {
                    "simulated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                    "did_reset": False,
                    "users_reset": 0,
                    "prices_applied": 9,
                },
            )()
            tick_result, sync_result = CronJobsService.run_test_time_warp_cycle()

        self.assertEqual(tick_result.prices_applied, 9)
        self.assertEqual(sync_result.users_processed, 1)
        self.assertGreater(sync_result.total_equity_usdt, Decimal("0"))
