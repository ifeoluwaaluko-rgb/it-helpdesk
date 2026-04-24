from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0006_ticket_external_message_id_ticketevent"),
        ("tickets", "0006_ticketevent_external_message_id"),
    ]

    operations = []
