from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings_app', '0002_integrationauditlog_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='integrationconfig',
            name='use_ssl',
            field=models.BooleanField(default=False),
        ),
    ]
