from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils import timezone

from .constants import (
    AGENT_IDS,
    DEFAULT_ADVISOR_IDS,
    DEFAULT_RISK_PROFILE,
    DEFAULT_STARTING_CASH,
    RISK_PROFILE_IDS,
    SUPPORTED_ASSET_IDS,
)


class TelegramIdentity(models.Model):
    telegram_user_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255, blank=True)
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"telegram:{self.telegram_user_id}"


class WalletAccount(models.Model):
    identity = models.OneToOneField(TelegramIdentity, on_delete=models.CASCADE, related_name="account")
    cash_balance = models.DecimalField(max_digits=20, decimal_places=2, default=DEFAULT_STARTING_CASH)
    initial_cash = models.DecimalField(max_digits=20, decimal_places=2, default=DEFAULT_STARTING_CASH)
    net_cash_flow = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"account:{self.identity.telegram_user_id}"


class AssetPosition(models.Model):
    account = models.ForeignKey(WalletAccount, on_delete=models.CASCADE, related_name="positions")
    asset_id = models.CharField(max_length=16, choices=[(asset, asset) for asset in SUPPORTED_ASSET_IDS])
    quantity = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    average_entry_price = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("account", "asset_id")


class PositionLot(models.Model):
    """FIFO lots used to track remaining inventory per asset position."""

    account = models.ForeignKey(WalletAccount, on_delete=models.CASCADE, related_name="position_lots")
    asset_id = models.CharField(max_length=16, choices=[(asset, asset) for asset in SUPPORTED_ASSET_IDS])
    remaining_quantity = models.DecimalField(max_digits=20, decimal_places=6)
    entry_price = models.DecimalField(max_digits=20, decimal_places=6)
    opened_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["account", "asset_id", "opened_at"]),
        ]


class TestOrder(models.Model):
    SIDE_BUY = "buy"
    SIDE_SELL = "sell"
    STATUS_FILLED = "filled"

    SIDE_CHOICES = (
        (SIDE_BUY, "Buy"),
        (SIDE_SELL, "Sell"),
    )

    STATUS_CHOICES = (
        (STATUS_FILLED, "Filled"),
    )

    account = models.ForeignKey(WalletAccount, on_delete=models.CASCADE, related_name="orders")
    side = models.CharField(max_length=8, choices=SIDE_CHOICES)
    asset_id = models.CharField(max_length=16, choices=[(asset, asset) for asset in SUPPORTED_ASSET_IDS])
    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    price = models.DecimalField(max_digits=20, decimal_places=6)
    notional = models.DecimalField(max_digits=20, decimal_places=6)
    realized_pnl = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True, default=None)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_FILLED)
    created_at = models.DateTimeField(auto_now_add=True)


class AgentPreference(models.Model):
    account = models.OneToOneField(WalletAccount, on_delete=models.CASCADE, related_name="agent_preference")
    selected_agents = models.JSONField(default=list)
    allocation = models.JSONField(default=dict)
    selected_advisors = models.JSONField(default=list)
    advisor_weights = models.JSONField(default=dict)
    initial_portfolio = models.JSONField(default=dict)
    risk_profile = models.CharField(
        max_length=16,
        choices=[(risk, risk) for risk in RISK_PROFILE_IDS],
        default=DEFAULT_RISK_PROFILE,
    )
    onboarding_completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    @staticmethod
    def default_selected_agents() -> list[str]:
        return list(AGENT_IDS)

    @staticmethod
    def default_allocation() -> dict[str, float]:
        equal_weight = 100.0 / float(len(AGENT_IDS))
        return {agent_id: equal_weight for agent_id in AGENT_IDS}

    @staticmethod
    def default_selected_advisors() -> list[str]:
        return list(DEFAULT_ADVISOR_IDS)

    @staticmethod
    def default_advisor_weights(selected_advisors: list[str] | None = None) -> dict[str, float]:
        advisor_ids = selected_advisors if selected_advisors is not None else list(DEFAULT_ADVISOR_IDS)
        if not advisor_ids:
            return {}
        equal_weight = round(100.0 / float(len(advisor_ids)), 2)
        weights = {advisor_id: equal_weight for advisor_id in advisor_ids}
        total = round(sum(weights.values()), 2)
        if total != 100.0:
            last_id = advisor_ids[-1]
            weights[last_id] = round(weights[last_id] + (100.0 - total), 2)
        return weights

    @staticmethod
    def default_risk_profile() -> str:
        return DEFAULT_RISK_PROFILE


class AssetPriceSnapshot(models.Model):
    """Stored market price snapshots used for live pricing and charts."""

    asset_id = models.CharField(max_length=16, choices=[(asset, asset) for asset in SUPPORTED_ASSET_IDS])
    price = models.DecimalField(max_digits=20, decimal_places=6)
    observed_at = models.DateTimeField(default=timezone.now, db_index=True)
    source = models.CharField(max_length=32, default="fmp")

    class Meta:
        indexes = [
            models.Index(fields=["asset_id", "-observed_at"]),
        ]


class BotJsonEvent(models.Model):
    """Raw JSON events captured by bot runtime for auditing/debugging."""

    source = models.CharField(max_length=32, default="telegram_bot", db_index=True)
    category = models.CharField(max_length=64, db_index=True)
    telegram_update_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    telegram_user_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    chat_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
