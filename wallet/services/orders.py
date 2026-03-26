"""Orders service for test-mode order execution and management."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
import time
from typing import TYPE_CHECKING

from django.db import transaction
from loguru import logger

from ..constants import TRADEABLE_ASSET_IDS
from ..models import AssetPosition, PositionLot, TestOrder, WalletAccount
from .prices import PricesService

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class OrderResult:
    """Result of a successful order execution."""

    order_id: int
    side: str
    asset_id: str
    quantity: Decimal
    price: Decimal
    notional: Decimal
    realized_pnl: Decimal
    status: str


class OrdersService:
    """Service for test-mode order execution and management."""
    MONEY_QUANT = Decimal("0.01")
    QUANTITY_QUANT = Decimal("0.000001")

    @staticmethod
    def _validate_asset(asset_id: str) -> None:
        """Validate that an asset is tradeable."""
        if asset_id not in TRADEABLE_ASSET_IDS:
            raise ValueError(f"Asset '{asset_id}' is not tradeable")

    @staticmethod
    def _validate_quantity(quantity: Decimal) -> None:
        """Validate order quantity."""
        if quantity <= Decimal("0"):
            raise ValueError("Quantity must be positive")

    @classmethod
    def _normalize_notional(cls, notional: Decimal) -> Decimal:
        normalized = notional.quantize(cls.MONEY_QUANT, rounding=ROUND_HALF_UP)
        if normalized <= 0:
            raise ValueError("Notional must be positive")
        return normalized

    @classmethod
    def _quantity_from_notional(cls, price: Decimal, notional: Decimal) -> Decimal:
        if price <= 0:
            raise ValueError("Asset price is unavailable")
        quantity = (notional / price).quantize(cls.QUANTITY_QUANT, rounding=ROUND_HALF_UP)
        cls._validate_quantity(quantity)
        return quantity

    @staticmethod
    def _bootstrap_legacy_lot_if_needed(position: AssetPosition) -> None:
        """Create a synthetic lot for pre-FIFO positions created before lots existed."""
        if position.quantity <= 0 or position.average_entry_price <= 0:
            return
        existing = PositionLot.objects.select_for_update().filter(
            account=position.account,
            asset_id=position.asset_id,
            remaining_quantity__gt=0,
        )
        if existing.exists():
            return
        PositionLot.objects.create(
            account=position.account,
            asset_id=position.asset_id,
            remaining_quantity=position.quantity,
            entry_price=position.average_entry_price,
        )

    @staticmethod
    def _recalculate_position_from_lots(position: AssetPosition) -> None:
        lots = list(
            PositionLot.objects.select_for_update()
            .filter(
                account=position.account,
                asset_id=position.asset_id,
                remaining_quantity__gt=0,
            )
            .order_by("opened_at", "id")
        )

        total_qty = Decimal("0")
        total_cost = Decimal("0")
        for lot in lots:
            total_qty += lot.remaining_quantity
            total_cost += lot.remaining_quantity * lot.entry_price

        position.quantity = total_qty
        if total_qty > 0:
            position.average_entry_price = total_cost / total_qty
        else:
            position.average_entry_price = Decimal("0")
        position.save(update_fields=["quantity", "average_entry_price", "updated_at"])

    @classmethod
    def create_buy_order(
        cls,
        account: WalletAccount,
        asset_id: str,
        quantity: Decimal,
    ) -> OrderResult:
        """Create and execute a buy order."""
        cls._validate_asset(asset_id)
        cls._validate_quantity(quantity)
        return cls._execute_buy_order_sync(account, asset_id, quantity, None)

    @classmethod
    def create_buy_order_by_notional(
        cls,
        account: WalletAccount,
        asset_id: str,
        notional: Decimal,
    ) -> OrderResult:
        cls._validate_asset(asset_id)
        return cls._execute_buy_order_sync(account, asset_id, None, notional)

    @classmethod
    def create_sell_order(
        cls,
        account: WalletAccount,
        asset_id: str,
        quantity: Decimal,
    ) -> OrderResult:
        """Create and execute a sell order."""
        cls._validate_asset(asset_id)
        cls._validate_quantity(quantity)
        return cls._execute_sell_order_sync(account, asset_id, quantity, None)

    @classmethod
    def create_sell_order_by_notional(
        cls,
        account: WalletAccount,
        asset_id: str,
        notional: Decimal,
    ) -> OrderResult:
        cls._validate_asset(asset_id)
        return cls._execute_sell_order_sync(account, asset_id, None, notional)

    @classmethod
    def _execute_buy_order_sync(
        cls,
        account: WalletAccount,
        asset_id: str,
        quantity: Decimal | None,
        notional_override: Decimal | None,
    ) -> OrderResult:
        """
        Execute a buy order synchronously.

        Deducts cash from account and creates/updates position.
        """
        price = PricesService.get_price(asset_id)
        if notional_override is not None:
            notional = cls._normalize_notional(notional_override)
            quantity = cls._quantity_from_notional(price, notional)
        elif quantity is not None:
            notional = cls._normalize_notional(price * quantity)
        else:
            raise ValueError("quantity or notional is required")

        if account.cash_balance < notional:
            raise ValueError("Insufficient cash balance")

        with transaction.atomic():
            # Lock account for update
            account = WalletAccount.objects.select_for_update().get(pk=account.pk)

            # Re-check after lock
            if account.cash_balance < notional:
                raise ValueError("Insufficient cash balance")

            # Deduct cash
            account.cash_balance -= notional
            account.save(update_fields=["cash_balance"])

            # Update or create position
            position, created = AssetPosition.objects.select_for_update().get_or_create(
                account=account,
                asset_id=asset_id,
                defaults={"quantity": Decimal("0"), "average_entry_price": Decimal("0")},
            )

            cls._bootstrap_legacy_lot_if_needed(position)
            PositionLot.objects.create(
                account=account,
                asset_id=asset_id,
                remaining_quantity=quantity,
                entry_price=price,
            )
            cls._recalculate_position_from_lots(position)

            # Create order record
            order = TestOrder.objects.create(
                account=account,
                side=TestOrder.SIDE_BUY,
                asset_id=asset_id,
                quantity=quantity,
                price=price,
                notional=notional,
                realized_pnl=Decimal("0"),
                status=TestOrder.STATUS_FILLED,
            )

        return OrderResult(
            order_id=order.id,
            side=order.side,
            asset_id=order.asset_id,
            quantity=order.quantity,
            price=order.price,
            notional=order.notional,
            realized_pnl=order.realized_pnl or Decimal("0"),
            status=order.status,
        )

    @classmethod
    def _execute_sell_order_sync(
        cls,
        account: WalletAccount,
        asset_id: str,
        quantity: Decimal | None,
        notional_override: Decimal | None,
    ) -> OrderResult:
        """
        Execute a sell order synchronously.

        Reduces position and adds cash to account.
        """
        price = PricesService.get_price(asset_id)
        if notional_override is not None:
            notional = cls._normalize_notional(notional_override)
            quantity = cls._quantity_from_notional(price, notional)
        elif quantity is not None:
            notional = cls._normalize_notional(price * quantity)
        else:
            raise ValueError("quantity or notional is required")

        with transaction.atomic():
            # Lock position for update
            try:
                position = AssetPosition.objects.select_for_update().get(
                    account=account,
                    asset_id=asset_id,
                )
            except AssetPosition.DoesNotExist:
                raise ValueError("No position to sell")

            # Lock account for update
            account = WalletAccount.objects.select_for_update().get(pk=account.pk)

            cls._bootstrap_legacy_lot_if_needed(position)
            remaining_to_sell = quantity
            realized_cost = Decimal("0")
            lots = list(
                PositionLot.objects.select_for_update()
                .filter(
                    account=account,
                    asset_id=asset_id,
                    remaining_quantity__gt=0,
                )
                .order_by("opened_at", "id")
            )
            for lot in lots:
                if remaining_to_sell <= 0:
                    break
                consume = min(lot.remaining_quantity, remaining_to_sell)
                realized_cost += consume * lot.entry_price
                lot.remaining_quantity -= consume
                remaining_to_sell -= consume
                lot.save(update_fields=["remaining_quantity"])

            if remaining_to_sell > 0:
                raise ValueError("Insufficient position to sell")

            cls._recalculate_position_from_lots(position)

            # Add cash
            account.cash_balance += notional
            account.save(update_fields=["cash_balance"])
            realized_pnl = notional - realized_cost

            # Create order record
            order = TestOrder.objects.create(
                account=account,
                side=TestOrder.SIDE_SELL,
                asset_id=asset_id,
                quantity=quantity,
                price=price,
                notional=notional,
                realized_pnl=realized_pnl,
                status=TestOrder.STATUS_FILLED,
            )

        return OrderResult(
            order_id=order.id,
            side=order.side,
            asset_id=order.asset_id,
            quantity=order.quantity,
            price=order.price,
            notional=order.notional,
            realized_pnl=order.realized_pnl or Decimal("0"),
            status=order.status,
        )

    @staticmethod
    def get_order(account: WalletAccount, order_id: int) -> TestOrder | None:
        """Get a specific order by ID."""
        try:
            return TestOrder.objects.select_related("account").get(
                id=order_id,
                account=account,
            )
        except TestOrder.DoesNotExist:
            return None

    @staticmethod
    def get_all_orders(account: WalletAccount) -> list[TestOrder]:
        """Get all orders for an account, ordered by creation date descending."""
        started_at = time.perf_counter()
        orders = list(
            TestOrder.objects.filter(account=account).order_by("-created_at")
        )
        logger.info(
            "orders.get_all_orders account_id={} orders={} db_ms={}",
            account.id,
            len(orders),
            round((time.perf_counter() - started_at) * 1000),
        )
        return orders
