from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("settings_app", "0005_fix_oauth_client_id_default"),
        ("settings_app", "0007_integrationconfig_auth_mode"),
    ]

    operations = []
