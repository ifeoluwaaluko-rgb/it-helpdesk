from django.db import migrations, models


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
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE tickets_ticket "
                        "ADD COLUMN IF NOT EXISTS external_message_id varchar(255);"
                    ),
                    reverse_sql=(
                        "ALTER TABLE tickets_ticket "
                        "DROP COLUMN IF EXISTS external_message_id;"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "UPDATE tickets_ticket "
                        "SET external_message_id = '' "
                        "WHERE external_message_id IS NULL;"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE tickets_ticket "
                        "ALTER COLUMN external_message_id SET DEFAULT '';"
                    ),
                    reverse_sql=(
                        "ALTER TABLE tickets_ticket "
                        "ALTER COLUMN external_message_id DROP DEFAULT;"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE tickets_ticket "
                        "ALTER COLUMN external_message_id SET NOT NULL;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE tickets_ticket "
                        "ALTER COLUMN external_message_id DROP NOT NULL;"
                    ),
                ),
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
