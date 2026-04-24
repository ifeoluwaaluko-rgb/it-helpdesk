from django.core.management.base import BaseCommand
from tickets.email_ingestion import fetch_and_create_tickets


class Command(BaseCommand):
    help = 'Fetch new emails from IMAP and create tickets'

    def handle(self, *args, **kwargs):
        count = fetch_and_create_tickets()
        self.stdout.write(self.style.SUCCESS(f'Created {count} ticket(s) from email.'))
