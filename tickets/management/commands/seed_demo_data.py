from datetime import date, timedelta
import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from assets.models import Asset, AssetCategory
from directory.models import Department, StaffMember
from knowledge.models import Article
from tickets.models import Profile, Ticket, TicketComment


class Command(BaseCommand):
    help = 'Seed demo data for local development or first-time empty deployments.'

    def add_arguments(self, parser):
        parser.add_argument('--if-empty', action='store_true', help='Only seed when there are no users, tickets, staff, assets, or articles.')

    def handle(self, *args, **options):
        if options.get('if_empty'):
            if any([
                User.objects.exists(),
                Ticket.objects.exists(),
                StaffMember.objects.exists(),
                Asset.objects.exists(),
                Article.objects.exists(),
            ]):
                self.stdout.write('ℹ️ Database already contains data — skipping seed.')
                return

        departments = {}
        for name in ['IT', 'Finance', 'HR', 'Operations', 'Engineering', 'Design']:
            departments[name], _ = Department.objects.get_or_create(name=name)

        users_data = [
            ('manager', 'manager', 'Mike', 'Adeyemi', 'manager', 'IT'),
            ('senior1', 'senior1', 'Sarah', 'Okonkwo', 'senior', 'IT'),
            ('consultant1', 'consultant1', 'James', 'Bello', 'consultant', 'IT'),
            ('consultant2', 'consultant2', 'Amaka', 'Chukwu', 'consultant', 'IT'),
            ('associate1', 'associate1', 'Tunde', 'Adeola', 'associate', 'IT'),
            ('associate2', 'associate2', 'Ngozi', 'Eze', 'associate', 'IT'),
        ]

        created_users = {}
        staff_records = {}
        for username, password, first, last, role, dept_name in users_data:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': f'{username}@company.com',
                    'is_staff': True,
                },
            )
            user.first_name = first
            user.last_name = last
            user.email = f'{username}@company.com'
            user.is_staff = True
            user.set_password(password)
            user.save()

            Profile.objects.update_or_create(user=user, defaults={'role': role})
            created_users.setdefault(role, []).append(user)

            staff_records[username], _ = StaffMember.objects.update_or_create(
                email=user.email,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'department': departments[dept_name],
                    'job_title': role.title(),
                    'is_active': True,
                },
            )

        requester_staff = [
            ('John', 'Doe', 'john.doe@company.com', 'Engineering', 'Developer'),
            ('Mary', 'Jones', 'mary.jones@company.com', 'Finance', 'Analyst'),
            ('Peter', 'Smith', 'peter.smith@company.com', 'Operations', 'Coordinator'),
            ('Fatima', 'Musa', 'fatima.musa@company.com', 'HR', 'HR Officer'),
            ('Emeka', 'Obi', 'emeka.obi@company.com', 'Finance', 'Accountant'),
            ('Aisha', 'Balogun', 'aisha.balogun@company.com', 'Design', 'Designer'),
        ]
        for first, last, email, dept_name, title in requester_staff:
            StaffMember.objects.update_or_create(
                email=email,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'department': departments[dept_name],
                    'job_title': title,
                    'is_active': True,
                },
            )

        cat_laptop, _ = AssetCategory.objects.get_or_create(name='Laptop', defaults={'icon': '💻'})
        cat_printer, _ = AssetCategory.objects.get_or_create(name='Printer', defaults={'icon': '🖨️'})
        cat_network, _ = AssetCategory.objects.get_or_create(name='Network Device', defaults={'icon': '🌐'})

        assets_data = [
            ('AST-1001', 'Dell Latitude 7420', cat_laptop, 'Dell', 'Latitude 7420', 'SN-D7420-01', 'active', staff_records['associate1']),
            ('AST-1002', 'HP LaserJet M404', cat_printer, 'HP', 'M404', 'SN-HPM404-02', 'active', None),
            ('AST-1003', 'Cisco Router 2901', cat_network, 'Cisco', '2901', 'SN-CISCO-03', 'spare', None),
        ]
        for asset_id, name, category, brand, model, serial, status, assigned_to in assets_data:
            Asset.objects.update_or_create(
                asset_id=asset_id,
                defaults={
                    'name': name,
                    'category': category,
                    'brand': brand,
                    'model': model,
                    'serial_number': serial,
                    'status': status,
                    'assigned_to': assigned_to,
                    'location': 'HQ Office',
                    'created_by': created_users['manager'][0],
                    'purchase_date': date.today() - timedelta(days=365),
                    'warranty_expiry': date.today() + timedelta(days=365),
                },
            )

        def pick(level):
            pool = created_users.get(level, [])
            if not pool:
                for fallback in ['associate', 'consultant', 'senior', 'manager']:
                    pool = created_users.get(fallback, [])
                    if pool:
                        break
            return random.choice(pool) if pool else None

        ticket_data = [
            ('Cannot connect to VPN from home', 'I have been trying to connect to the office VPN since morning but it keeps timing out. Using Windows 11.', 'john.doe@company.com', 'network', 'high', 'consultant', 4, 'in_progress'),
            ('Password reset request', 'I forgot my password and cannot log in to my machine. Please help urgently.', 'mary.jones@company.com', 'password', 'medium', 'associate', 4, 'resolved'),
            ('Printer not working on 3rd floor', 'The HP printer near the conference room is offline. Multiple staff affected.', 'peter.smith@company.com', 'printer', 'low', 'associate', 8, 'open'),
            ('New staff onboarding - Chidi Obi', 'New developer joining Monday. Needs laptop, email, GitHub and Jira access.', 'hr@company.com', 'onboarding', 'high', 'senior', 24, 'open'),
            ('Outlook keeps crashing on startup', 'Every time I open Outlook it crashes after 2 seconds. Tried restarting. Using Office 365.', 'fatima.musa@company.com', 'email', 'medium', 'consultant', 8, 'in_progress'),
            ('Request access to Finance shared drive', 'I have been moved to Finance team and need access to their shared folder.', 'emeka.obi@company.com', 'access', 'medium', 'consultant', 8, 'open'),
            ('Laptop screen flickering badly', 'My Dell laptop screen has been flickering since yesterday. Makes it hard to work.', 'aisha.balogun@company.com', 'hardware', 'high', 'consultant', 8, 'open'),
            ('Cannot install Figma — need admin rights', 'Trying to install Figma for design project but need admin rights to proceed.', 'design@company.com', 'software', 'low', 'associate', 24, 'resolved'),
        ]

        if not Ticket.objects.exists():
            for title, desc, email, category, priority, level, sla_hours, status in ticket_data:
                created_at = timezone.now() - timedelta(hours=random.randint(1, 72))
                resolved_at = None
                if status in ['resolved', 'closed']:
                    resolved_at = created_at + timedelta(hours=random.randint(1, max(2, sla_hours)))
                ticket = Ticket.objects.create(
                    title=title,
                    description=desc,
                    user_email=email,
                    requester_name=email.split('@')[0].replace('.', ' ').title(),
                    category=category,
                    priority=priority,
                    required_level=level,
                    assigned_to=pick(level),
                    sla_hours=sla_hours,
                    status=status,
                    created_at=created_at,
                    resolved_at=resolved_at,
                    first_response_at=created_at + timedelta(minutes=random.randint(5, 90)),
                    channel='email',
                )
                if status != 'open':
                    TicketComment.objects.create(
                        ticket=ticket,
                        author=ticket.assigned_to or created_users['manager'][0],
                        body='Initial triage completed.',
                        created_at=created_at + timedelta(minutes=15),
                    )

        articles = [
            ('Resetting Windows Passwords', 'Use the standard password reset workflow and confirm identity before reset.', 'password', 'password,windows,login'),
            ('VPN Troubleshooting Guide', 'Check network connectivity, client version, and MFA prompts before escalating.', 'network', 'vpn,network,remote'),
            ('Fixing Common Printer Faults', 'Restart spooler, verify connectivity, and check printer queue.', 'printer', 'printer,queue,offline'),
        ]
        for title, content, category, tags in articles:
            Article.objects.get_or_create(
                title=title,
                defaults={
                    'content': content,
                    'category': category,
                    'tags': tags,
                    'created_by': created_users['manager'][0],
                },
            )

        self.stdout.write(self.style.SUCCESS('✅ Demo data seeded successfully.'))
