from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wallet", "0005_positionlot"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentpreference",
            name="risk_profile",
            field=models.CharField(
                choices=[("low", "low"), ("medium", "medium"), ("high", "high")],
                default="medium",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="agentpreference",
            name="selected_advisors",
            field=models.JSONField(default=list),
        ),
    ]
