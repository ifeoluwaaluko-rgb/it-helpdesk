from django.db import migrations, models


def sync_auth_mode(apps, schema_editor):
    connection = schema_editor.connection
    table_name = "settings_app_integrationconfig"

    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table_name)

    column_names = {column.name for column in description}
    if "auth_mode" not in column_names:
        schema_editor.execute(
            "ALTER TABLE settings_app_integrationconfig "
            "ADD COLUMN auth_mode varchar(30) NOT NULL DEFAULT 'basic';"
        )
        return

    if connection.vendor == "postgresql":
        schema_editor.execute(
            "UPDATE settings_app_integrationconfig "
            "SET auth_mode = 'basic' "
            "WHERE auth_mode IS NULL OR auth_mode = '';"
        )
        schema_editor.execute(
            "ALTER TABLE settings_app_integrationconfig "
            "ALTER COLUMN auth_mode SET DEFAULT 'basic';"
        )
        schema_editor.execute(
            "ALTER TABLE settings_app_integrationconfig "
            "ALTER COLUMN auth_mode SET NOT NULL;"
        )


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("settings_app", "0006_merge_use_ssl_and_existing_merge"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(sync_auth_mode, noop_reverse),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="integrationconfig",
                    name="auth_mode",
                    field=models.CharField(blank=True, default="basic", max_length=30),
                ),
            ],
        ),
    ]
