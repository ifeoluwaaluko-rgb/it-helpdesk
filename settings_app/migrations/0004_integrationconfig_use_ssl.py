from django.db import migrations, models


def sync_use_ssl(apps, schema_editor):
    connection = schema_editor.connection
    table_name = "settings_app_integrationconfig"

    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table_name)

    column_names = {column.name for column in description}
    if "use_ssl" not in column_names:
        schema_editor.execute(
            "ALTER TABLE settings_app_integrationconfig "
            "ADD COLUMN use_ssl bool NOT NULL DEFAULT FALSE;"
        )
        return

    if connection.vendor == "postgresql":
        schema_editor.execute(
            "UPDATE settings_app_integrationconfig "
            "SET use_ssl = FALSE "
            "WHERE use_ssl IS NULL;"
        )
        schema_editor.execute(
            "ALTER TABLE settings_app_integrationconfig "
            "ALTER COLUMN use_ssl SET DEFAULT FALSE;"
        )
        schema_editor.execute(
            "ALTER TABLE settings_app_integrationconfig "
            "ALTER COLUMN use_ssl SET NOT NULL;"
        )


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("settings_app", "0003_state_only_encrypted_field_names"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(sync_use_ssl, noop_reverse),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="integrationconfig",
                    name="use_ssl",
                    field=models.BooleanField(default=False),
                ),
            ],
        ),
    ]
