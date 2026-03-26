from __future__ import annotations

from decimal import Decimal

from django.db import models

from wallet.models import TelegramIdentity

from .constants import ONCHAIN_USDT_ASSET_ID, SUPPORTED_ONCHAIN_ASSET_IDS


class OnchainWallet(models.Model):
    identity = models.OneToOneField(TelegramIdentity, on_delete=models.CASCADE, related_name="onchain_wallet")
    address = models.CharField(max_length=128, unique=True)
    seed_phrase = models.TextField()
    version = models.CharField(max_length=16, default="v5r1")
    usdt_balance = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    realized_pnl_usdt = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    cumulative_invested_usdt = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OnchainPosition(models.Model):
    wallet = models.ForeignKey(OnchainWallet, on_delete=models.CASCADE, related_name="positions")
    asset_id = models.CharField(max_length=16, choices=[(asset, asset) for asset in SUPPORTED_ONCHAIN_ASSET_IDS])
    quantity = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    average_entry_price = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("wallet", "asset_id")


class OnchainOrder(models.Model):
    SIDE_BUY = "buy"
    SIDE_SELL = "sell"
    SIDE_WITHDRAW = "withdraw"
    STATUS_FILLED = "filled"

    wallet = models.ForeignKey(OnchainWallet, on_delete=models.CASCADE, related_name="orders")
    side = models.CharField(max_length=16)
    asset_id = models.CharField(max_length=16, default=ONCHAIN_USDT_ASSET_ID)
    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    price = models.DecimalField(max_digits=20, decimal_places=6)
    notional = models.DecimalField(max_digits=20, decimal_places=6)
    offer_asset_id = models.CharField(max_length=16)
    offer_amount = models.DecimalField(max_digits=20, decimal_places=6)
    receive_asset_id = models.CharField(max_length=16)
    receive_amount = models.DecimalField(max_digits=20, decimal_places=6)
    status = models.CharField(max_length=16, default=STATUS_FILLED)
    destination_address = models.CharField(max_length=128, blank=True)
    external_order_id = models.CharField(max_length=128, blank=True)
    tx_hash = models.CharField(max_length=256, blank=True)
    execution_details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
