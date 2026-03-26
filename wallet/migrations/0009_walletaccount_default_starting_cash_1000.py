from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wallet", "0008_agentpreference_initial_portfolio"),
    ]

    operations = [
        migrations.AlterField(
            model_name="walletaccount",
            name="cash_balance",
            field=models.DecimalField(decimal_places=2, default=Decimal("1000.00"), max_digits=20),
        ),
        migrations.AlterField(
            model_name="walletaccount",
            name="initial_cash",
            field=models.DecimalField(decimal_places=2, default=Decimal("1000.00"), max_digits=20),
        ),
    ]
