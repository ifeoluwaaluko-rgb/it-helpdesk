
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings_app', '0003_integrationconfig_use_ssl'),
    ]

    operations = [
        migrations.AddField(
            model_name='integrationconfig',
            name='auth_mode',
            field=models.CharField(choices=[('password', 'SMTP password / app password'), ('gmail_api_oauth', 'Gmail API OAuth2')], default='password', max_length=30),
        ),
        migrations.AddField(
            model_name='integrationconfig',
            name='oauth_client_id',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='integrationconfig',
            name='oauth_token_uri',
            field=models.CharField(blank=True, default='https://oauth2.googleapis.com/token', max_length=255),
        ),
        migrations.AddField(
            model_name='integrationconfig',
            name='_oauth_client_secret',
            field=models.TextField(blank=True, db_column='oauth_client_secret'),
        ),
        migrations.AddField(
            model_name='integrationconfig',
            name='_oauth_refresh_token',
            field=models.TextField(blank=True, db_column='oauth_refresh_token'),
        ),
    ]
