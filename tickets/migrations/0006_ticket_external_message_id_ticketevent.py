
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
        migrations.CreateModel(
            name='TicketEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('created', 'Created'), ('commented', 'Commented'), ('assigned', 'Assigned'), ('reassigned', 'Reassigned'), ('picked_up', 'Picked Up'), ('status_changed', 'Status Changed'), ('resolved', 'Resolved'), ('closed', 'Closed'), ('reopened', 'Reopened'), ('category_updated', 'Category Updated')], max_length=30)),
                ('from_status', models.CharField(blank=True, max_length=20)),
                ('to_status', models.CharField(blank=True, max_length=20)),
                ('note', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='tickets.ticket')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
