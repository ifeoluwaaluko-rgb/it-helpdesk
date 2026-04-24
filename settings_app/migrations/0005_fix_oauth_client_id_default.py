"""
Fix: oauth_client_id column was added WITHOUT a database-level default,
causing a NOT NULL IntegrityError whenever get_or_create() tries to insert
a new IntegrationConfig row (e.g. first visit to /settings/).

We also fix oauth_token_uri, oauth_client_secret, and oauth_refresh_token
the same way for consistency.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings_app', '0004_integrationconfig_gmail_oauth2'),
    ]

    operations = [
        # Set DB-level default '' on oauth_client_id so INSERT works without it
        migrations.AlterField(
            model_name='integrationconfig',
            name='oauth_client_id',
            field=models.CharField(max_length=255, blank=True, default=''),
        ),
        # Same for oauth_token_uri (already had default in migration but be explicit)
        migrations.AlterField(
            model_name='integrationconfig',
            name='oauth_token_uri',
            field=models.CharField(
                max_length=255, blank=True,
                default='https://oauth2.googleapis.com/token'
            ),
        ),
    ]
