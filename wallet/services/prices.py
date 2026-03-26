from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
from django.conf import settings
from django.utils import timezone as django_timezone
from loguru import logger

from ..constants import TEST_PRICES, TRADEABLE_ASSET_IDS, SupportedAsset
from ..models import AssetPriceSnapshot
from .test_time_warp import TestTimeWarpService

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class PriceInfo:
    """Price information for an asset."""

    asset_id: str
    price: Decimal


class PricesService:
    """Service for retrieving and storing market prices."""

    FMP_SYMBOL_BY_ASSET: dict[str, str] = {
        SupportedAsset.TSLAX.value: "TSLA",
        SupportedAsset.HOODX.value: "HOOD",
        SupportedAsset.AMZNX.value: "AMZN",
        SupportedAsset.NVDAX.value: "NVDA",
        SupportedAsset.COINX.value: "COIN",
        SupportedAsset.GOOGLX.value: "GOOGL",
        SupportedAsset.AAPLX.value: "AAPL",
        SupportedAsset.MSTRX.value: "MSTR",
    }

    @classmethod
    def _is_test_time_warp_enabled(cls) -> bool:
        return bool(getattr(settings, "TEST_TIME_WARP_ENABLED", False))

    @classmethod
    def _is_fmp_enabled(cls) -> bool:
        return bool(getattr(settings, "FMP_ENABLED", False) and getattr(settings, "FMP_API_KEY", ""))

    @classmethod
    def _seed_default_prices(cls) -> None:
        for asset_id, price in TEST_PRICES.items():
            exists = AssetPriceSnapshot.objects.filter(asset_id=asset_id).exists()
            if exists:
                continue
            AssetPriceSnapshot.objects.create(asset_id=asset_id, price=price, source="seed")

    @classmethod
    def _latest_snapshot(cls, asset_id: str) -> AssetPriceSnapshot | None:
        return (
            AssetPriceSnapshot.objects.filter(asset_id=asset_id)
            .order_by("-observed_at")
            .first()
        )

    @classmethod
    def _needs_refresh(cls, max_age_seconds: int = 120) -> bool:
        latest = (
            AssetPriceSnapshot.objects.filter(asset_id__in=TRADEABLE_ASSET_IDS)
            .order_by("-observed_at")
            .first()
        )
        if latest is None:
            return True
        age = django_timezone.now() - latest.observed_at
        return age.total_seconds() > max_age_seconds

    @classmethod
    def _fetch_quotes_from_fmp(cls) -> dict[str, Decimal]:
        base_url = "https://financialmodelingprep.com/stable/quote"
        api_key = str(getattr(settings, "FMP_API_KEY", ""))
        prices: dict[str, Decimal] = {}

        with httpx.Client(timeout=8.0) as client:
            for asset_id, symbol in cls.FMP_SYMBOL_BY_ASSET.items():
                response = client.get(base_url, params={"symbol": symbol, "apikey": api_key})
                response.raise_for_status()
                payload = response.json()
                if not payload:
                    continue
                raw_price = payload[0].get("price")
                if raw_price is None:
                    continue
                prices[asset_id] = Decimal(str(raw_price))

        return prices

    @classmethod
    def _store_quotes(cls, quotes: dict[str, Decimal], source: str = "fmp") -> None:
        for asset_id, price in quotes.items():
            AssetPriceSnapshot.objects.create(
                asset_id=asset_id,
                price=price,
                source=source,
            )
        # Keep explicit 1.0 for USDt
        AssetPriceSnapshot.objects.create(
            asset_id=SupportedAsset.USDT.value,
            price=Decimal("1"),
            source=source,
        )

    @classmethod
    def sync_latest_prices(cls, force: bool = False) -> None:
        cls._seed_default_prices()
        if cls._is_test_time_warp_enabled():
            tick = TestTimeWarpService.maybe_advance_on_request()
            if tick is None:
                logger.info("PricesService.sync_latest_prices: test_time_warp enabled, tick skipped by throttling")
            else:
                logger.info(
                    "PricesService.sync_latest_prices: test_time_warp tick simulated_at={} prices_applied={}",
                    tick.simulated_at.isoformat(),
                    tick.prices_applied,
                )
            return
        if not cls._is_fmp_enabled():
            logger.info("PricesService.sync_latest_prices: FMP disabled, using stored/fallback prices")
            return
        if not force and not cls._needs_refresh():
            return
        try:
            quotes = cls._fetch_quotes_from_fmp()
            if quotes:
                cls._store_quotes(quotes, source="fmp")
                logger.info(f"PricesService.sync_latest_prices: stored {len(quotes)} FMP quotes")
        except Exception:
            # Keep app functional with previously stored prices.
            logger.warning("PricesService.sync_latest_prices: failed to refresh from FMP, using fallback prices")
            return

    @classmethod
    def _fetch_history_from_fmp(cls, asset_id: str, days: int = 30) -> list[tuple[datetime, Decimal]]:
        symbol = cls.FMP_SYMBOL_BY_ASSET.get(asset_id)
        if not symbol:
            return []
        api_key = str(getattr(settings, "FMP_API_KEY", ""))
        response = httpx.get(
            "https://financialmodelingprep.com/stable/historical-price-eod/full",
            params={"symbol": symbol, "apikey": api_key},
            timeout=10.0,
        )
        response.raise_for_status()
        historical = response.json()
        if isinstance(historical, dict):
            historical = historical.get("historical", [])
        result: list[tuple[datetime, Decimal]] = []
        for row in historical[:days]:
            date_str = row.get("date")
            close = row.get("close")
            if not date_str or close is None:
                continue
            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            result.append((dt, Decimal(str(close))))
        return result

    @classmethod
    def _fetch_intraday_history_from_fmp(
        cls,
        asset_id: str,
        date_from: str,
        date_to: str,
    ) -> list[tuple[datetime, Decimal]]:
        symbol = cls.FMP_SYMBOL_BY_ASSET.get(asset_id)
        if not symbol:
            return []
        api_key = str(getattr(settings, "FMP_API_KEY", ""))
        response = httpx.get(
            "https://financialmodelingprep.com/stable/historical-chart/1min",
            params={
                "symbol": symbol,
                "from": date_from,
                "to": date_to,
                "apikey": api_key,
            },
            timeout=20.0,
        )
        if response.status_code == 402:
            raise PermissionError("FMP intraday endpoint is not available for current subscription")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return []
        result: list[tuple[datetime, Decimal]] = []
        for row in payload:
            dt_raw = row.get("date")
            close = row.get("close")
            if not dt_raw or close is None:
                continue
            # FMP returns e.g. "2026-03-24 15:59:00"
            observed_at = datetime.strptime(dt_raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            result.append((observed_at, Decimal(str(close))))
        return result

    @classmethod
    def ensure_history(cls, asset_id: str, days: int = 30, force: bool = False) -> None:
        if asset_id == SupportedAsset.USDT.value:
            cls._seed_default_prices()
            return

        since = django_timezone.now() - timedelta(days=days + 2)
        existing_count = AssetPriceSnapshot.objects.filter(asset_id=asset_id, observed_at__gte=since).count()
        if not force and existing_count >= days:
            return

        if not cls._is_fmp_enabled():
            logger.info(f"PricesService.ensure_history: FMP disabled for {asset_id}, using stored/fallback history")
            return
        try:
            history = cls._fetch_history_from_fmp(asset_id, days=days)
        except Exception:
            logger.warning(f"PricesService.ensure_history: failed to fetch history for {asset_id}, using fallback")
            return

        existing_dates = {
            snap.observed_at.date()
            for snap in AssetPriceSnapshot.objects.filter(asset_id=asset_id, observed_at__gte=since)
        }
        for observed_dt, price in history:
            if observed_dt.date() in existing_dates:
                continue
            AssetPriceSnapshot.objects.create(
                asset_id=asset_id,
                price=price,
                observed_at=observed_dt,
                source="fmp_history",
            )
        logger.info(f"PricesService.ensure_history: stored history points for {asset_id}")

    @classmethod
    def load_historical_prices(cls, days: int = 365, force: bool = False) -> dict[str, int]:
        """
        Bulk load historical prices for all tradeable assets used by charts.

        Returns number of snapshots currently available per asset in requested window.
        """
        cls._seed_default_prices()
        result: dict[str, int] = {}
        for asset_id in TRADEABLE_ASSET_IDS:
            cls.ensure_history(asset_id, days=days, force=force)
            since = django_timezone.now() - timedelta(days=days + 2)
            result[asset_id] = AssetPriceSnapshot.objects.filter(
                asset_id=asset_id,
                observed_at__gte=since,
            ).count()
        return result

    @classmethod
    def purge_price_history(cls) -> int:
        """Delete all stored snapshots so history can be rebuilt from scratch."""
        deleted_count, _ = AssetPriceSnapshot.objects.all().delete()
        logger.info("PricesService.purge_price_history: deleted={} snapshots", deleted_count)
        return int(deleted_count)

    @classmethod
    def load_intraday_prices(
        cls,
        days: int = 365,
        window_days: int = 5,
    ) -> dict[str, int]:
        """
        Load 1-minute history for all tradeable assets.

        Splits the requested range into small windows to avoid oversized responses.
        Raises PermissionError when minute endpoint is restricted by subscription.
        """
        if not cls._is_fmp_enabled():
            logger.info("PricesService.load_intraday_prices: FMP disabled")
            return {asset_id: 0 for asset_id in TRADEABLE_ASSET_IDS}

        now_dt = django_timezone.now()
        start_dt = now_dt - timedelta(days=days)
        if window_days < 1:
            window_days = 1

        stored_per_asset: dict[str, int] = {}

        for asset_id in TRADEABLE_ASSET_IDS:
            cursor = start_dt
            inserted = 0
            while cursor < now_dt:
                next_cursor = min(cursor + timedelta(days=window_days), now_dt)
                try:
                    rows = cls._fetch_intraday_history_from_fmp(
                        asset_id=asset_id,
                        date_from=cursor.strftime("%Y-%m-%d"),
                        date_to=next_cursor.strftime("%Y-%m-%d"),
                    )
                except PermissionError:
                    raise
                except Exception:
                    rows = []

                for observed_at, price in rows:
                    AssetPriceSnapshot.objects.create(
                        asset_id=asset_id,
                        price=price,
                        observed_at=observed_at,
                        source="fmp_intraday_1min",
                    )
                    inserted += 1
                cursor = next_cursor

            stored_per_asset[asset_id] = inserted
            logger.info("PricesService.load_intraday_prices: asset={} inserted={}", asset_id, inserted)

        AssetPriceSnapshot.objects.create(
            asset_id=SupportedAsset.USDT.value,
            price=Decimal("1"),
            source="fmp_intraday_1min",
        )
        return stored_per_asset

    @staticmethod
    def get_price(asset_id: str) -> Decimal:
        """Get the current price for an asset."""
        PricesService._seed_default_prices()
        if PricesService._is_test_time_warp_enabled():
            TestTimeWarpService.maybe_advance_on_request()
        if asset_id == SupportedAsset.USDT.value:
            return Decimal("1")
        latest = PricesService._latest_snapshot(asset_id)
        if latest is not None:
            return latest.price
        return TEST_PRICES.get(asset_id, Decimal("0"))

    @staticmethod
    def get_all_prices() -> dict[str, Decimal]:
        """Get all asset prices."""
        PricesService._seed_default_prices()
        if PricesService._is_test_time_warp_enabled():
            TestTimeWarpService.maybe_advance_on_request()
        prices: dict[str, Decimal] = {}
        for asset_id in TEST_PRICES:
            if asset_id == SupportedAsset.USDT.value:
                prices[asset_id] = Decimal("1")
            else:
                latest = PricesService._latest_snapshot(asset_id)
                prices[asset_id] = latest.price if latest else TEST_PRICES[asset_id]
        return prices

    @staticmethod
    def get_price_history(asset_id: str, days: int = 30) -> list[dict[str, float | str]]:
        """Get historical daily prices for charts."""
        PricesService._seed_default_prices()
        if asset_id == SupportedAsset.USDT.value:
            today = django_timezone.now().date()
            return [
                {"date": (today - timedelta(days=idx)).isoformat(), "value": 1.0}
                for idx in range(days - 1, -1, -1)
            ]

        since = django_timezone.now() - timedelta(days=days + 2)
        snapshots = list(
            AssetPriceSnapshot.objects.filter(asset_id=asset_id, observed_at__gte=since)
            .order_by("observed_at")
        )
        if not snapshots:
            fallback = TEST_PRICES.get(asset_id, Decimal("0"))
            today = django_timezone.now().date()
            return [
                {"date": (today - timedelta(days=idx)).isoformat(), "value": float(fallback)}
                for idx in range(days - 1, -1, -1)
            ]

        intraday = [snap for snap in snapshots if snap.source.startswith("fmp_intraday_1min")]
        if intraday:
            return [
                {"date": snap.observed_at.strftime("%Y-%m-%d %H:%M:%S"), "value": float(snap.price)}
                for snap in intraday[-2000:]
            ]

        by_day: dict[str, Decimal] = {}
        for snap in snapshots:
            by_day[snap.observed_at.date().isoformat()] = snap.price
        return [{"date": date, "value": float(price)} for date, price in sorted(by_day.items())[-days:]]

    @staticmethod
    def get_price_info(asset_id: str) -> PriceInfo | None:
        """Get price info for an asset, or None if not found."""
        if asset_id not in TEST_PRICES:
            return None
        return PriceInfo(asset_id=asset_id, price=PricesService.get_price(asset_id))

    @staticmethod
    def calculate_notional(asset_id: str, quantity: Decimal) -> Decimal:
        """Calculate notional value of a quantity at current price."""
        price = PricesService.get_price(asset_id)
        return price * quantity

    @staticmethod
    def is_valid_asset(asset_id: str) -> bool:
        """Check if an asset ID is supported."""
        return asset_id in TEST_PRICES
