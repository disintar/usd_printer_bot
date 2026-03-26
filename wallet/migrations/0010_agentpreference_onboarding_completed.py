from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wallet", "0009_walletaccount_default_starting_cash_1000"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentpreference",
            name="onboarding_completed",
            field=models.BooleanField(default=False),
        ),
    ]
