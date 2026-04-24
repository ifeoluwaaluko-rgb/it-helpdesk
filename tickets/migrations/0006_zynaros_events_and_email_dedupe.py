from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0005_ticket_first_response_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='external_message_id',
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name='ticket',
            name='resolved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_tickets', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='TicketEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('created', 'Created'), ('commented', 'Commented'), ('assigned', 'Assigned'), ('reassigned', 'Reassigned'), ('status_changed', 'Status changed'), ('resolved', 'Resolved'), ('category_changed', 'Category changed'), ('edited', 'Edited'), ('email_received', 'Email received')], max_length=40)),
                ('message', models.CharField(blank=True, max_length=500)),
                ('old_value', models.CharField(blank=True, max_length=255)),
                ('new_value', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='tickets.ticket')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
