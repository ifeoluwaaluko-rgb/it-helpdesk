from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0003_alter_ticket_status_ticketedithistory'),
    ]

    operations = [
        migrations.CreateModel(
            name='TicketAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='ticket_attachments/')),
                ('filename', models.CharField(blank=True, max_length=255)),
                ('content_type', models.CharField(blank=True, max_length=100)),
                ('is_image', models.BooleanField(default=False)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('source', models.CharField(
                    choices=[('email', 'Email'), ('manual', 'Manual')],
                    default='email', max_length=20)),
                ('ticket', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments', to='tickets.ticket')),
            ],
            options={'ordering': ['uploaded_at']},
        ),
    ]
