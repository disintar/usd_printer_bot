from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from loguru import logger

from ..models import WalletAccount
from .prices import PricesService
from .test_time_warp import TestTimeWarpService, TimeWarpTickResult
from .wallet_summary import WalletSummaryService


@dataclass(frozen=True)
class CronSyncResult:
    """Summary of one cron sync cycle."""

    users_processed: int
    total_equity_usdt: Decimal


class CronJobsService:
    """Background cron jobs for market data and portfolio recalculation."""

    @classmethod
    def _recalculate_all_users(cls) -> CronSyncResult:
        users_processed = 0
        total_equity = Decimal("0")
        accounts = WalletAccount.objects.select_related("identity").all()
        for account in accounts:
            balance = WalletSummaryService.get_balance(account)
            users_processed += 1
            total_equity += balance.total_balance_usdt

        logger.info(
            "CronJobsService.sync_prices_and_recalculate_pnl: users_processed={} total_equity_usdt={}",
            users_processed,
            total_equity.quantize(Decimal("0.01")),
        )
        return CronSyncResult(
            users_processed=users_processed,
            total_equity_usdt=total_equity.quantize(Decimal("0.01")),
        )

    @classmethod
    def sync_prices_and_recalculate_pnl(cls) -> CronSyncResult:
        PricesService.sync_latest_prices(force=True)
        return cls._recalculate_all_users()

    @classmethod
    def run_test_time_warp_cycle(cls) -> tuple[TimeWarpTickResult, CronSyncResult]:
        tick_result = TestTimeWarpService.advance_and_sync_prices()
        sync_result = cls._recalculate_all_users()
        logger.info(
            "CronJobsService.run_test_time_warp_cycle: simulated_at={} reset={} users_reset={} users_processed={} total_equity_usdt={}",
            tick_result.simulated_at.isoformat(),
            tick_result.did_reset,
            tick_result.users_reset,
            sync_result.users_processed,
            sync_result.total_equity_usdt,
        )
        return tick_result, sync_result
