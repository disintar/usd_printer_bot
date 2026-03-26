from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import threading
import time

from django.conf import settings
from django.utils import timezone as django_timezone
from loguru import logger

from ..constants import TEST_PRICES, TRADEABLE_ASSET_IDS
from ..models import AssetPosition, AssetPriceSnapshot, PositionLot, TestOrder, WalletAccount


@dataclass(frozen=True)
class TimeWarpTickResult:
    """Summary of one accelerated-time tick."""

    simulated_at: datetime
    did_reset: bool
    users_reset: int
    prices_applied: int


@dataclass(frozen=True)
class TimeWarpClockInfo:
    """Current backend test-time clock information."""

    real_now: datetime
    simulated_now: datetime
    enabled: bool
    window_days: int
    hours_per_tick: int


class TestTimeWarpService:
    """Accelerated test-time market clock and historical-price playback."""

    HISTORY_SOURCES: tuple[str, ...] = ("fmp_intraday_1min", "fmp_history")
    SNAPSHOT_SOURCE: str = "test_time_warp"
    WINDOW_DAYS: int = 60
    HOURS_PER_TICK: int = 1
    INITIAL_RESET_CASH: Decimal = Decimal("1000.00")
    MIN_TICK_MOVE_RATIO: Decimal = Decimal("0.0005")

    _simulated_at: datetime | None = None
    _anchor_real_at: datetime | None = None
    _last_request_tick_real_at: datetime | None = None
    _request_tick_lock: threading.Lock = threading.Lock()
    REQUEST_TICK_MIN_INTERVAL_SECONDS: float = 1.0

    @classmethod
    def is_enabled(cls) -> bool:
        """Return whether test-time warp mode is enabled."""
        return bool(getattr(settings, "TEST_TIME_WARP_ENABLED", False))

    @classmethod
    def reset_runtime_state(cls) -> None:
        """Clear in-memory simulated clock state."""
        cls._simulated_at = None
        cls._anchor_real_at = None
        cls._last_request_tick_real_at = None
        logger.info("TestTimeWarpService.reset_runtime_state: cleared simulated clock")

    @classmethod
    def set_simulated_time_for_tests(cls, simulated_at: datetime) -> None:
        """Override simulated clock for deterministic tests."""
        cls._simulated_at = cls._to_utc(simulated_at)
        cls._anchor_real_at = cls._real_now(None)
        cls._last_request_tick_real_at = None
        logger.info(
            "TestTimeWarpService.set_simulated_time_for_tests: simulated_at={}",
            cls._simulated_at.isoformat(),
        )

    @classmethod
    def maybe_advance_on_request(
        cls,
        real_now: datetime | None = None,
        min_interval_seconds: float | None = None,
    ) -> TimeWarpTickResult | None:
        """Advance one simulated tick at most once per interval during API request bursts."""
        if not cls.is_enabled():
            return None
        interval = (
            float(min_interval_seconds)
            if min_interval_seconds is not None
            else float(cls.REQUEST_TICK_MIN_INTERVAL_SECONDS)
        )
        if interval < 0:
            interval = 0.0

        current_real_now = cls._real_now(real_now)
        started_at = time.perf_counter()
        with cls._request_tick_lock:
            if cls._last_request_tick_real_at is not None:
                elapsed_seconds = (current_real_now - cls._last_request_tick_real_at).total_seconds()
                if elapsed_seconds < interval:
                    logger.debug(
                        "TestTimeWarpService.maybe_advance_on_request: skipped elapsed_seconds={} interval_seconds={}",
                        round(elapsed_seconds, 3),
                        interval,
                    )
                    return None
            cls._last_request_tick_real_at = current_real_now

        result = cls.advance_and_sync_prices(real_now=current_real_now)
        logger.info(
            "TestTimeWarpService.maybe_advance_on_request: simulated_at={} did_reset={} users_reset={} prices_applied={} total_ms={}",
            result.simulated_at.isoformat(),
            result.did_reset,
            result.users_reset,
            result.prices_applied,
            round((time.perf_counter() - started_at) * 1000),
        )
        return result

    @classmethod
    def _to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def _real_now(cls, real_now: datetime | None) -> datetime:
        if real_now is None:
            return django_timezone.now().astimezone(timezone.utc)
        return cls._to_utc(real_now)

    @classmethod
    def _bootstrap_if_needed(cls, real_now: datetime) -> None:
        if cls._simulated_at is not None:
            return
        cls._simulated_at = real_now - timedelta(days=cls.WINDOW_DAYS)
        cls._anchor_real_at = real_now
        logger.info(
            "TestTimeWarpService._bootstrap_if_needed: initialized simulated_at={}",
            cls._simulated_at.isoformat(),
        )

    @classmethod
    def _synthetic_price_at(cls, asset_id: str, simulated_at: datetime) -> Decimal:
        base = TEST_PRICES.get(asset_id, Decimal("1"))
        hour_key = int(simulated_at.timestamp() // 3600)
        digest = hashlib.md5(f"{asset_id}:{hour_key}".encode()).hexdigest()
        noise_int = int(digest[:8], 16)
        noise_ratio = Decimal(noise_int % 2001) / Decimal("100000")
        direction = Decimal("-1") if noise_int % 2 == 0 else Decimal("1")
        drift = direction * noise_ratio
        candidate = base * (Decimal("1") + drift)
        if candidate <= Decimal("0"):
            return base
        return candidate.quantize(Decimal("0.000001"))

    @classmethod
    def _history_price_at(cls, asset_id: str, simulated_at: datetime) -> Decimal:
        history = AssetPriceSnapshot.objects.filter(
            asset_id=asset_id,
            source__in=cls.HISTORY_SOURCES,
        )
        before = history.filter(observed_at__lte=simulated_at).order_by("-observed_at").first()

        after = history.filter(observed_at__gt=simulated_at).order_by("observed_at").first()
        if before is not None and after is not None and after.observed_at > before.observed_at:
            span_seconds = (after.observed_at - before.observed_at).total_seconds()
            if span_seconds > 0:
                elapsed_seconds = (simulated_at - before.observed_at).total_seconds()
                if elapsed_seconds < 0:
                    elapsed_seconds = 0
                if elapsed_seconds > span_seconds:
                    elapsed_seconds = span_seconds
                ratio = Decimal(str(elapsed_seconds / span_seconds))
                delta = after.price - before.price
                return before.price + (delta * ratio)

        if before is not None:
            return before.price
        if after is not None:
            return after.price

        latest = history.order_by("-observed_at").first()
        if latest is not None:
            return latest.price

        return cls._synthetic_price_at(asset_id, simulated_at)

    @classmethod
    def get_clock_info(cls, real_now: datetime | None = None) -> TimeWarpClockInfo:
        """Return real and simulated time used by accelerated test mode."""
        current_real_now = cls._real_now(real_now)
        cls._bootstrap_if_needed(current_real_now)
        simulated_now = cls._simulated_at
        anchor_real_at = cls._anchor_real_at
        if simulated_now is None or anchor_real_at is None:
            simulated_now = current_real_now - timedelta(days=cls.WINDOW_DAYS)
        else:
            elapsed_real_seconds = (current_real_now - anchor_real_at).total_seconds()
            if elapsed_real_seconds < 0:
                elapsed_real_seconds = 0
            simulated_now = simulated_now + timedelta(hours=elapsed_real_seconds)
        return TimeWarpClockInfo(
            real_now=current_real_now,
            simulated_now=simulated_now,
            enabled=cls.is_enabled(),
            window_days=cls.WINDOW_DAYS,
            hours_per_tick=cls.HOURS_PER_TICK,
        )

    @classmethod
    def _build_quotes_for_simulated_time(cls, simulated_at: datetime) -> dict[str, Decimal]:
        quotes: dict[str, Decimal] = {}
        for asset_id in TRADEABLE_ASSET_IDS:
            price = cls._history_price_at(asset_id, simulated_at)
            latest = AssetPriceSnapshot.objects.filter(
                asset_id=asset_id,
                source=cls.SNAPSHOT_SOURCE,
            ).order_by("-observed_at").first()
            if latest is not None and latest.price == price:
                hour_key = int(simulated_at.timestamp() // 3600)
                digest = hashlib.md5(f"tick:{asset_id}:{hour_key}".encode()).hexdigest()
                sign = Decimal("1") if int(digest[0], 16) % 2 == 0 else Decimal("-1")
                move = latest.price * cls.MIN_TICK_MOVE_RATIO * sign
                adjusted = latest.price + move
                if adjusted > Decimal("0"):
                    price = adjusted.quantize(Decimal("0.000001"))
            quotes[asset_id] = price
        quotes["USDt"] = Decimal("1")
        return quotes

    @classmethod
    def _store_quotes(cls, quotes: dict[str, Decimal]) -> int:
        observed_at = django_timezone.now()
        stored = 0
        for asset_id, price in quotes.items():
            AssetPriceSnapshot.objects.create(
                asset_id=asset_id,
                price=price,
                observed_at=observed_at,
                source=cls.SNAPSHOT_SOURCE,
            )
            stored += 1
        return stored

    @classmethod
    def _reset_accounts(cls) -> int:
        positions_deleted, _ = AssetPosition.objects.all().delete()
        lots_deleted, _ = PositionLot.objects.all().delete()
        orders_deleted, _ = TestOrder.objects.all().delete()
        users_reset = WalletAccount.objects.count()
        WalletAccount.objects.all().update(
            cash_balance=cls.INITIAL_RESET_CASH,
            initial_cash=cls.INITIAL_RESET_CASH,
            net_cash_flow=Decimal("0.00"),
        )
        logger.warning(
            "TestTimeWarpService._reset_accounts: users_reset={} positions_deleted={} lots_deleted={} orders_deleted={} initial_cash={}",
            users_reset,
            positions_deleted,
            lots_deleted,
            orders_deleted,
            cls.INITIAL_RESET_CASH,
        )
        return users_reset

    @classmethod
    def advance_and_sync_prices(cls, real_now: datetime | None = None) -> TimeWarpTickResult:
        """Advance simulated market time and write one historical-price snapshot set."""
        started_at = time.perf_counter()
        current_real_now = cls._real_now(real_now)
        cls._bootstrap_if_needed(current_real_now)
        if cls._simulated_at is None:
            raise RuntimeError("simulated clock is not initialized")

        simulated_next = cls._simulated_at + timedelta(hours=cls.HOURS_PER_TICK)
        did_reset = False
        users_reset = 0

        if simulated_next >= current_real_now:
            did_reset = True
            users_reset = cls._reset_accounts()
            simulated_next = current_real_now - timedelta(days=cls.WINDOW_DAYS)
            logger.warning(
                "TestTimeWarpService.advance_and_sync_prices: cycle reset triggered new_simulated_at={}",
                simulated_next.isoformat(),
            )

        build_started_at = time.perf_counter()
        quotes = cls._build_quotes_for_simulated_time(simulated_next)
        build_ms = round((time.perf_counter() - build_started_at) * 1000)

        store_started_at = time.perf_counter()
        prices_applied = cls._store_quotes(quotes)
        store_ms = round((time.perf_counter() - store_started_at) * 1000)
        cls._simulated_at = simulated_next
        cls._anchor_real_at = current_real_now

        logger.info(
            "TestTimeWarpService.advance_and_sync_prices: simulated_at={} did_reset={} users_reset={} prices_applied={} build_ms={} store_ms={} total_ms={}",
            simulated_next.isoformat(),
            did_reset,
            users_reset,
            prices_applied,
            build_ms,
            store_ms,
            round((time.perf_counter() - started_at) * 1000),
        )
        return TimeWarpTickResult(
            simulated_at=simulated_next,
            did_reset=did_reset,
            users_reset=users_reset,
            prices_applied=prices_applied,
        )
