from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wallet", "0007_agentpreference_advisor_weights"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentpreference",
            name="initial_portfolio",
            field=models.JSONField(default=dict),
        ),
    ]
