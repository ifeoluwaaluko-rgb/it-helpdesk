import time
from django.core.management.base import BaseCommand
from tickets.email_ingestion import fetch_and_create_tickets


class Command(BaseCommand):
    help = 'Fetch new emails from IMAP and create tickets'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true', help='Keep polling for emails forever')
        parser.add_argument('--sleep', type=int, default=60, help='Seconds to sleep between polls in loop mode')

    def handle(self, *args, **options):
        if options['loop']:
            sleep_seconds = max(15, int(options['sleep'] or 60))
            self.stdout.write(self.style.SUCCESS(
                f'Email poller started. Checking inbox every {sleep_seconds} seconds.'
            ))
            while True:
                count = fetch_and_create_tickets()
                self.stdout.write(f'Processed inbox. Created {count} ticket(s).')
                time.sleep(sleep_seconds)
        else:
            count = fetch_and_create_tickets()
            self.stdout.write(self.style.SUCCESS(f'Created {count} ticket(s) from email.'))
