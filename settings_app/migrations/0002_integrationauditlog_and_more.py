from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('settings_app', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='IntegrationAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('integration', models.CharField(max_length=30)),
                ('action', models.CharField(choices=[('save', 'Saved'), ('test', 'Tested'), ('toggle', 'Toggled')], max_length=20)),
                ('status', models.CharField(default='success', max_length=20)),
                ('message', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AlterField(
            model_name='integrationconfig',
            name='integration',
            field=models.CharField(choices=[
                ('email_smtp', 'Email – SMTP (Outbound)'),
                ('email_imap', 'Email – IMAP (Inbound)'),
                ('microsoft_graph', 'Microsoft Graph'),
                ('generic_webhook', 'Generic Webhook'),
                ('whatsapp', 'WhatsApp Business Cloud API'),
                ('teams', 'Microsoft Teams Webhook'),
                ('slack', 'Slack Webhook'),
                ('openai', 'OpenAI / AI Provider'),
            ], max_length=30, unique=True),
        ),
    ]
