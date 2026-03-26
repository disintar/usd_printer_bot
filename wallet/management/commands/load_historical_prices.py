from __future__ import annotations

from django.core.management.base import BaseCommand
from loguru import logger

from wallet.services.prices import PricesService


class Command(BaseCommand):
    help = "Purge old prices and load 1-minute history (or daily fallback) from FMP."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="How many days of history to load per asset (default: 365)",
        )
        parser.add_argument(
            "--window-days",
            type=int,
            default=5,
            help="Window size for 1-minute requests in days (default: 5)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force refresh attempt even if enough history already exists",
        )
        parser.add_argument(
            "--no-purge",
            action="store_true",
            help="Do not delete old snapshots before loading",
        )
        parser.add_argument(
            "--no-fallback",
            action="store_true",
            help="Do not fallback to daily history if 1-minute endpoint is restricted",
        )

    def handle(self, *args, **options) -> None:
        days = max(1, int(options["days"]))
        window_days = max(1, int(options["window_days"]))
        force = bool(options["force"])
        no_purge = bool(options["no_purge"])
        no_fallback = bool(options["no_fallback"])

        logger.info(
            "load_historical_prices: start days={} window_days={} force={} purge={}",
            days,
            window_days,
            force,
            not no_purge,
        )

        if not no_purge:
            PricesService.purge_price_history()

        mode = "1min"
        try:
            counts = PricesService.load_intraday_prices(days=days, window_days=window_days)
        except PermissionError:
            if no_fallback:
                raise
            mode = "1day_fallback"
            logger.warning(
                "load_historical_prices: 1-minute endpoint restricted; fallback to daily history",
            )
            counts = PricesService.load_historical_prices(days=days, force=force)

        self.stdout.write(f"Historical price snapshots available (mode={mode}):")
        for asset_id in sorted(counts):
            self.stdout.write(f" - {asset_id}: {counts[asset_id]}")
        logger.info("load_historical_prices: completed")
