from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("settings_app", "0002_integrationauditlog_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameField(
                    model_name="integrationconfig",
                    old_name="password",
                    new_name="_password",
                ),
                migrations.RenameField(
                    model_name="integrationconfig",
                    old_name="access_token",
                    new_name="_access_token",
                ),
            ],
        ),
    ]
