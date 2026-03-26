from __future__ import annotations

import decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("wallet", "0007_agentpreference_advisor_weights"),
    ]

    operations = [
        migrations.CreateModel(
            name="OnchainWallet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("address", models.CharField(max_length=128, unique=True)),
                ("seed_phrase", models.TextField()),
                ("version", models.CharField(default="v5r1", max_length=16)),
                ("usdt_balance", models.DecimalField(decimal_places=6, default=decimal.Decimal("0"), max_digits=20)),
                ("realized_pnl_usdt", models.DecimalField(decimal_places=6, default=decimal.Decimal("0"), max_digits=20)),
                ("cumulative_invested_usdt", models.DecimalField(decimal_places=6, default=decimal.Decimal("0"), max_digits=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("identity", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="onchain_wallet", to="wallet.telegramidentity")),
            ],
        ),
        migrations.CreateModel(
            name="OnchainOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("side", models.CharField(max_length=16)),
                ("asset_id", models.CharField(default="USDt", max_length=16)),
                ("quantity", models.DecimalField(decimal_places=6, max_digits=20)),
                ("price", models.DecimalField(decimal_places=6, max_digits=20)),
                ("notional", models.DecimalField(decimal_places=6, max_digits=20)),
                ("offer_asset_id", models.CharField(max_length=16)),
                ("offer_amount", models.DecimalField(decimal_places=6, max_digits=20)),
                ("receive_asset_id", models.CharField(max_length=16)),
                ("receive_amount", models.DecimalField(decimal_places=6, max_digits=20)),
                ("status", models.CharField(default="filled", max_length=16)),
                ("destination_address", models.CharField(blank=True, max_length=128)),
                ("external_order_id", models.CharField(blank=True, max_length=128)),
                ("tx_hash", models.CharField(blank=True, max_length=256)),
                ("execution_details", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("wallet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="orders", to="onchain.onchainwallet")),
            ],
        ),
        migrations.CreateModel(
            name="OnchainPosition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("asset_id", models.CharField(choices=[("TSLAx", "TSLAx"), ("HOODx", "HOODx"), ("AMZNx", "AMZNx"), ("NVDAx", "NVDAx"), ("COINx", "COINx"), ("GOOGLx", "GOOGLx"), ("AAPLx", "AAPLx"), ("MSTRx", "MSTRx")], max_length=16)),
                ("quantity", models.DecimalField(decimal_places=6, default=decimal.Decimal("0"), max_digits=20)),
                ("average_entry_price", models.DecimalField(decimal_places=6, default=decimal.Decimal("0"), max_digits=20)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("wallet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="positions", to="onchain.onchainwallet")),
            ],
            options={"unique_together": {("wallet", "asset_id")}},
        ),
    ]
