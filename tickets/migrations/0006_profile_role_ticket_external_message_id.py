from django.db import migrations, models


def sync_external_message_id(apps, schema_editor):
    connection = schema_editor.connection
    table_name = "tickets_ticket"
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table_name)
    column_names = {column.name for column in description}

    if "external_message_id" not in column_names:
        schema_editor.execute(
            "ALTER TABLE tickets_ticket "
            "ADD COLUMN external_message_id varchar(255) NOT NULL DEFAULT '';"
        )
        return

    if connection.vendor == "postgresql":
        schema_editor.execute(
            "UPDATE tickets_ticket "
            "SET external_message_id = '' "
            "WHERE external_message_id IS NULL;"
        )
        schema_editor.execute(
            "ALTER TABLE tickets_ticket "
            "ALTER COLUMN external_message_id SET DEFAULT '';"
        )
        schema_editor.execute(
            "ALTER TABLE tickets_ticket "
            "ALTER COLUMN external_message_id SET NOT NULL;"
        )


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0005_ticket_first_response_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profile",
            name="role",
            field=models.CharField(
                choices=[
                    ("associate", "Associate"),
                    ("consultant", "Consultant"),
                    ("senior", "Senior"),
                    ("manager", "Manager"),
                    ("superadmin", "Super Admin"),
                ],
                default="associate",
                max_length=20,
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(sync_external_message_id, noop_reverse),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="ticket",
                    name="external_message_id",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
            ],
        ),
    ]
