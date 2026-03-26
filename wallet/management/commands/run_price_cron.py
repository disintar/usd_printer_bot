from __future__ import annotations

import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from loguru import logger

from wallet.services.cron_jobs import CronJobsService


class Command(BaseCommand):
    help = "Run background price sync cron every N seconds (default 60)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--interval-seconds",
            type=int,
            default=getattr(settings, "PRICE_CRON_INTERVAL_SECONDS", 60),
            help="Seconds between sync cycles (default: 60)",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run one cycle and exit",
        )
        parser.add_argument(
            "--test-time-warp",
            action="store_true",
            help="Run accelerated test clock (1 tick = 1h simulated time) using historical prices",
        )

    def handle(self, *args, **options) -> None:
        interval_seconds = int(options["interval_seconds"])
        run_once = bool(options["once"])
        test_time_warp = bool(options["test_time_warp"])

        if interval_seconds < 1:
            interval_seconds = 1

        logger.info(
            "run_price_cron: started interval_seconds={} once={} test_time_warp={}",
            interval_seconds,
            run_once,
            test_time_warp,
        )

        while True:
            started = timezone.now()
            try:
                if test_time_warp:
                    CronJobsService.run_test_time_warp_cycle()
                else:
                    CronJobsService.sync_prices_and_recalculate_pnl()
            except Exception as exc:
                logger.exception("run_price_cron: cycle failed: {}", exc)

            if run_once:
                logger.info("run_price_cron: completed single cycle")
                return

            elapsed = (timezone.now() - started).total_seconds()
            sleep_for = max(0.0, float(interval_seconds) - float(elapsed))
            time.sleep(sleep_for)
