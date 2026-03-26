from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wallet", "0006_agentpreference_selected_advisors_and_risk_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentpreference",
            name="advisor_weights",
            field=models.JSONField(default=dict),
        ),
    ]
