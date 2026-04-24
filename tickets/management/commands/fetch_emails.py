import time
from django.core.management.base import BaseCommand
from tickets.email_ingestion import fetch_and_create_tickets


class Command(BaseCommand):
    help = "Fetch inbound IMAP emails and create tickets"

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')
        parser.add_argument('--sleep', type=int, default=15)

    def handle(self, *args, **options):
        if options['loop']:
            while True:
                created = fetch_and_create_tickets()
                self.stdout.write(f"Processed inbound email. Created {created} ticket(s).")
                time.sleep(options['sleep'])
        else:
            created = fetch_and_create_tickets()
            self.stdout.write(f"Processed inbound email. Created {created} ticket(s).")
