from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.test import TestCase, override_settings

from wallet.models import (
    AssetPosition,
    AssetPriceSnapshot,
    PositionLot,
    TelegramIdentity,
    TestOrder,
    WalletAccount,
)
from wallet.constants import TRADEABLE_ASSET_IDS
from wallet.services.test_time_warp import TestTimeWarpService


class TestTimeWarpServiceTests(TestCase):
    def setUp(self) -> None:
        TestTimeWarpService.reset_runtime_state()

    def tearDown(self) -> None:
        TestTimeWarpService.reset_runtime_state()

    def test_advance_uses_historical_price_for_current_simulated_time(self) -> None:
        real_now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        expected_simulated_time = real_now - timedelta(days=60) + timedelta(hours=1)
        AssetPriceSnapshot.objects.create(
            asset_id="AAPLx",
            price=Decimal("123.45"),
            observed_at=expected_simulated_time,
            source="fmp_intraday_1min",
        )

        result = TestTimeWarpService.advance_and_sync_prices(real_now=real_now)

        self.assertFalse(result.did_reset)
        self.assertEqual(result.simulated_at, expected_simulated_time)
        latest = AssetPriceSnapshot.objects.filter(
            asset_id="AAPLx",
            source=TestTimeWarpService.SNAPSHOT_SOURCE,
        ).order_by("-id").first()
        self.assertIsNotNone(latest)
        if latest is None:
            return
        self.assertEqual(latest.price, Decimal("123.45"))

    def test_advance_resets_accounts_and_positions_when_cycle_reaches_now(self) -> None:
        real_now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        identity = TelegramIdentity.objects.create(telegram_user_id=4242, token="tok4242")
        account = WalletAccount.objects.create(
            identity=identity,
            cash_balance=Decimal("777.00"),
            initial_cash=Decimal("10000.00"),
            net_cash_flow=Decimal("88.00"),
        )
        AssetPosition.objects.create(
            account=account,
            asset_id="AAPLx",
            quantity=Decimal("2"),
            average_entry_price=Decimal("100"),
        )
        PositionLot.objects.create(
            account=account,
            asset_id="AAPLx",
            remaining_quantity=Decimal("2"),
            entry_price=Decimal("100"),
        )
        TestOrder.objects.create(
            account=account,
            side=TestOrder.SIDE_BUY,
            asset_id="AAPLx",
            quantity=Decimal("2"),
            price=Decimal("100"),
            notional=Decimal("200"),
            status=TestOrder.STATUS_FILLED,
        )

        TestTimeWarpService.set_simulated_time_for_tests(real_now - timedelta(minutes=30))
        result = TestTimeWarpService.advance_and_sync_prices(real_now=real_now)

        self.assertTrue(result.did_reset)
        self.assertEqual(result.users_reset, 1)
        self.assertEqual(result.simulated_at, real_now - timedelta(days=60))

        account.refresh_from_db()
        self.assertEqual(account.cash_balance, Decimal("1000.00"))
        self.assertEqual(account.initial_cash, Decimal("1000.00"))
        self.assertEqual(account.net_cash_flow, Decimal("0.00"))
        self.assertEqual(AssetPosition.objects.count(), 0)
        self.assertEqual(PositionLot.objects.count(), 0)
        self.assertEqual(TestOrder.objects.count(), 0)

    def test_advance_changes_fallback_price_without_history(self) -> None:
        real_now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        TestTimeWarpService.advance_and_sync_prices(real_now=real_now)
        first = AssetPriceSnapshot.objects.filter(
            asset_id="NVDAx",
            source=TestTimeWarpService.SNAPSHOT_SOURCE,
        ).order_by("-id").first()
        self.assertIsNotNone(first)
        if first is None:
            return

        second_now = real_now + timedelta(seconds=1)
        TestTimeWarpService.advance_and_sync_prices(real_now=second_now)
        second = AssetPriceSnapshot.objects.filter(
            asset_id="NVDAx",
            source=TestTimeWarpService.SNAPSHOT_SOURCE,
        ).order_by("-id").first()
        self.assertIsNotNone(second)
        if second is None:
            return
        self.assertNotEqual(first.price, second.price)

    def test_advance_changes_all_tradeable_prices_each_tick(self) -> None:
        real_now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        TestTimeWarpService.advance_and_sync_prices(real_now=real_now)

        first_by_asset = {
            asset_id: AssetPriceSnapshot.objects.filter(
                asset_id=asset_id,
                source=TestTimeWarpService.SNAPSHOT_SOURCE,
            ).order_by("-id").first()
            for asset_id in TRADEABLE_ASSET_IDS
        }

        TestTimeWarpService.advance_and_sync_prices(real_now=real_now + timedelta(seconds=1))

        for asset_id in TRADEABLE_ASSET_IDS:
            second = AssetPriceSnapshot.objects.filter(
                asset_id=asset_id,
                source=TestTimeWarpService.SNAPSHOT_SOURCE,
            ).order_by("-id").first()
            self.assertIsNotNone(second)
            first = first_by_asset[asset_id]
            self.assertIsNotNone(first)
            if first is None or second is None:
                continue
            self.assertNotEqual(first.price, second.price, asset_id)

    @override_settings(TEST_TIME_WARP_ENABLED=True)
    def test_maybe_advance_on_request_throttles_burst_calls(self) -> None:
        real_now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        first = TestTimeWarpService.maybe_advance_on_request(
            real_now=real_now,
            min_interval_seconds=60.0,
        )
        second = TestTimeWarpService.maybe_advance_on_request(
            real_now=real_now + timedelta(seconds=1),
            min_interval_seconds=60.0,
        )

        self.assertIsNotNone(first)
        self.assertIsNone(second)

    @override_settings(TEST_TIME_WARP_ENABLED=True)
    def test_maybe_advance_on_request_advances_after_interval(self) -> None:
        real_now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        first = TestTimeWarpService.maybe_advance_on_request(
            real_now=real_now,
            min_interval_seconds=1.0,
        )
        second = TestTimeWarpService.maybe_advance_on_request(
            real_now=real_now + timedelta(seconds=2),
            min_interval_seconds=1.0,
        )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        if first is None or second is None:
            return
        self.assertGreater(second.simulated_at, first.simulated_at)
