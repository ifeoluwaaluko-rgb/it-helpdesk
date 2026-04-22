from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='IntegrationConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('integration', models.CharField(
                    choices=[
                        ('email_smtp', 'Email – SMTP (Outbound)'),
                        ('email_imap', 'Email – IMAP (Inbound)'),
                        ('whatsapp', 'WhatsApp Business Cloud API'),
                        ('teams', 'Microsoft Teams Webhook'),
                        ('slack', 'Slack Webhook'),
                    ],
                    max_length=30, unique=True)),
                ('is_active', models.BooleanField(default=False)),
                ('host', models.CharField(blank=True, max_length=255)),
                ('port', models.IntegerField(blank=True, null=True)),
                ('username', models.CharField(blank=True, max_length=255)),
                ('use_tls', models.BooleanField(default=True)),
                ('webhook_url', models.CharField(blank=True, max_length=500)),
                ('phone_number_id', models.CharField(blank=True, max_length=50)),
                ('wa_business_id', models.CharField(blank=True, max_length=50)),
                ('password', models.TextField(blank=True, db_column='password')),
                ('access_token', models.TextField(blank=True, db_column='access_token')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='auth.user')),
            ],
            options={'ordering': ['integration'],
                     'verbose_name': 'Integration Config',
                     'verbose_name_plural': 'Integration Configs'},
        ),
    ]
