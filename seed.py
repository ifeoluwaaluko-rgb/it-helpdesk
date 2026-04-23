"""
Seed script. Safe to run multiple times because it uses get_or_create and exits
early when tickets already exist.
"""
import os
import random

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "helpdesk.settings")
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone

from assets.models import Asset, AssetCategory, AssetHistory
from directory.models import Department, StaffMember
from knowledge.models import Article
from tickets.models import Profile, Ticket, TicketComment


if Ticket.objects.exists():
    print("Database already seeded. Skipping.")
    raise SystemExit(0)


users_data = [
    ("manager", "manager", "Mike", "Adeyemi", "manager"),
    ("senior1", "senior1", "Sarah", "Okonkwo", "senior"),
    ("consultant1", "consultant1", "James", "Bello", "consultant"),
    ("consultant2", "consultant2", "Amaka", "Chukwu", "consultant"),
    ("associate1", "associate1", "Tunde", "Adeola", "associate"),
    ("associate2", "associate2", "Ngozi", "Eze", "associate"),
]

created_users = {}
for username, password, first, last, role in users_data:
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": first,
            "last_name": last,
            "email": f"{username}@company.com",
            "is_staff": True,
        },
    )
    user.set_password(password)
    user.save()
    Profile.objects.update_or_create(user=user, defaults={"role": role})
    created_users.setdefault(role, []).append(user)

print(f"Created {len(users_data)} users")


def pick(level):
    pool = created_users.get(level, [])
    if not pool:
        for fallback in ["associate", "consultant", "senior", "manager"]:
            pool = created_users.get(fallback, [])
            if pool:
                break
    return random.choice(pool) if pool else None


ticket_data = [
    (
        "Cannot connect to VPN from home",
        "I have been trying to connect to the office VPN since morning but it keeps timing out. Using Windows 11.",
        "john.doe@company.com",
        "network",
        "high",
        "consultant",
        4,
        "in_progress",
    ),
    (
        "Password reset request",
        "I forgot my password and cannot log in to my machine. Please help urgently.",
        "mary.jones@company.com",
        "password",
        "medium",
        "associate",
        4,
        "resolved",
    ),
    (
        "Printer not working on 3rd floor",
        "The HP printer near the conference room is offline. Multiple staff affected.",
        "peter.smith@company.com",
        "printer",
        "low",
        "associate",
        8,
        "open",
    ),
    (
        "New staff onboarding - Chidi Obi",
        "New developer joining Monday. Needs laptop, email, GitHub and Jira access.",
        "hr@company.com",
        "onboarding",
        "high",
        "senior",
        24,
        "open",
    ),
    (
        "Outlook keeps crashing on startup",
        "Every time I open Outlook it crashes after 2 seconds. Tried restarting. Using Office 365.",
        "fatima.musa@company.com",
        "email",
        "medium",
        "consultant",
        8,
        "in_progress",
    ),
    (
        "Request access to Finance shared drive",
        "I have been moved to Finance team and need access to their shared folder.",
        "emeka.obi@company.com",
        "access",
        "medium",
        "consultant",
        8,
        "open",
    ),
    (
        "Laptop screen flickering badly",
        "My Dell laptop screen has been flickering since yesterday. Makes it hard to work.",
        "aisha.balogun@company.com",
        "hardware",
        "high",
        "consultant",
        8,
        "open",
    ),
    (
        "Cannot install Figma - need admin rights",
        "Trying to install Figma for design project but need admin rights to proceed.",
        "design@company.com",
        "software",
        "low",
        "associate",
        24,
        "resolved",
    ),
    (
        "Entire office internet is down",
        "No internet across the building since 9am. Affects all departments.",
        "ceo@company.com",
        "network",
        "critical",
        "manager",
        1,
        "resolved",
    ),
    (
        "Email not syncing on phone",
        "My work email stopped syncing on my iPhone. Tried removing and re-adding the account.",
        "tola.adebayo@company.com",
        "email",
        "medium",
        "consultant",
        8,
        "open",
    ),
]

tickets = []
for title, description, email, category, priority, level, sla_hours, status in ticket_data:
    assignee = pick(level)
    resolved_at = None
    if status == "resolved":
        resolved_at = timezone.now() - timezone.timedelta(
            hours=random.randint(1, sla_hours)
        )
    ticket = Ticket.objects.create(
        title=title,
        description=description,
        user_email=email,
        category=category,
        priority=priority,
        required_level=level,
        sla_hours=sla_hours,
        status=status,
        assigned_to=assignee,
        external_message_id="",
        resolved_at=resolved_at,
    )
    Ticket.objects.filter(pk=ticket.pk).update(
        created_at=timezone.now() - timezone.timedelta(hours=random.randint(2, 72))
    )
    tickets.append(ticket)

print(f"Created {len(tickets)} tickets")

TicketComment.objects.create(
    ticket=tickets[0],
    author=pick("consultant"),
    body="Checked firewall logs. UDP port 1194 appears blocked. Escalating to the network team.",
)
TicketComment.objects.create(
    ticket=tickets[1],
    author=pick("associate"),
    body="Reset password via AD. User confirmed they can now log in.",
)
TicketComment.objects.create(
    ticket=tickets[4],
    author=pick("consultant"),
    body="Cleared Outlook profile cache. Issue persists. Next step is a repair install.",
)
print("Added sample comments")

articles = [
    (
        "How to Fix VPN Timeout Issues",
        "network",
        "vpn, windows, remote",
        "1. Ensure UDP port 1194 is open on your router.\n"
        "2. Switch from UDP to TCP in VPN client settings.\n"
        "3. Flush DNS by running ipconfig /flushdns in Command Prompt.\n"
        "4. Reinstall the VPN client if the issue persists.\n"
        "5. Contact IT if none of the above works.",
    ),
    (
        "Password Reset Procedure",
        "password",
        "password, active-directory, account",
        "1. Go to https://aka.ms/sspr or call IT on ext. 100.\n"
        "2. Verify identity via phone or backup email.\n"
        "3. Set a new password with at least 8 characters, an uppercase letter, a number, and a symbol.\n"
        "4. Log in and update saved passwords in your browser.",
    ),
    (
        "Printer Offline Troubleshooting",
        "printer",
        "printer, hp, offline",
        "1. Check that the printer is powered on and connected to the network.\n"
        "2. On Windows, open Devices & Printers, right-click the printer, choose See what's printing, open Printer, and clear Use Printer Offline.\n"
        "3. Restart the Print Spooler service.\n"
        "4. Reinstall the printer driver if needed.",
    ),
    (
        "New Staff Onboarding Checklist",
        "onboarding",
        "onboarding, new-hire, setup",
        "Day 1 setup:\n"
        "- Create AD account and email address\n"
        "- Assign a laptop from IT inventory\n"
        "- Install Office, Teams, and the VPN client\n"
        "- Add the user to relevant distribution lists\n"
        "- Create Jira and GitHub accounts\n"
        "- Brief the user on security policy",
    ),
]

for title, category, tags, content in articles:
    Article.objects.create(
        title=title,
        category=category,
        tags=tags,
        content=content,
        created_by=pick("senior"),
        source_ticket=tickets[0] if category == "network" else None,
    )

print(f"Created {len(articles)} knowledge articles")
print("\nSeed complete. Login credentials:")
for username, password, first, last, role in users_data:
    print(f"  {role:<12} -> username: {username:<15} password: {password}")


departments = {}
for name in ["Engineering", "Finance", "HR", "Marketing", "Operations", "Sales"]:
    department, _ = Department.objects.get_or_create(name=name)
    departments[name] = department

directory_staff = [
    ("John", "Doe", "john.doe@company.com", "+2348001000001", "Engineering", "Senior Developer"),
    ("Mary", "Jones", "mary.jones@company.com", "+2348001000002", "HR", "HR Manager"),
    ("Peter", "Smith", "peter.smith@company.com", "+2348001000003", "Finance", "Finance Manager"),
    ("Fatima", "Musa", "fatima.musa@company.com", "+2348001000004", "Marketing", "Brand Manager"),
    ("Emeka", "Obi", "emeka.obi@company.com", "+2348001000005", "Operations", "Operations Lead"),
    ("Aisha", "Balogun", "aisha.balogun@company.com", "+2348001000006", "Engineering", "Frontend Developer"),
    ("Tola", "Adebayo", "tola.adebayo@company.com", "+2348001000007", "Sales", "Sales Representative"),
    ("Chidi", "Obi", "chidi.obi@company.com", "+2348001000008", "Engineering", "New Hire"),
]

for first_name, last_name, email, phone, department_name, job_title in directory_staff:
    StaffMember.objects.get_or_create(
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "department": departments[department_name],
            "job_title": job_title,
        },
    )

print(f"Created {len(directory_staff)} staff directory entries")

admin_user = User.objects.filter(is_staff=True).first()
categories = {}
for name, icon in [
    ("Computers", "PC"),
    ("Printers", "PR"),
    ("Network Devices", "NW"),
    ("Mobile Devices", "PH"),
    ("Software", "SW"),
    ("SIM Cards", "SIM"),
]:
    category, _ = AssetCategory.objects.get_or_create(name=name, defaults={"icon": icon})
    categories[name] = category

sample_assets = [
    ("LAPTOP-001", "Dell XPS 15", "Computers", "Dell", "XPS 15", "SN-DX001", "Floor 2", "active", "john.doe@company.com"),
    ("LAPTOP-002", "MacBook Pro 14", "Computers", "Apple", "MacBook Pro", "SN-MB002", "Floor 1", "active", "aisha.balogun@company.com"),
    ("PRINTER-001", "HP LaserJet Pro", "Printers", "HP", "LaserJet Pro 400", "SN-HP001", "3rd Floor", "active", None),
    ("SWITCH-001", "Cisco 24-Port Switch", "Network Devices", "Cisco", "Catalyst 2960", "SN-CS001", "Server Room", "active", None),
    ("PHONE-001", "Samsung Galaxy A54", "Mobile Devices", "Samsung", "Galaxy A54", "SN-SG001", "Reception", "active", "mary.jones@company.com"),
    ("LAPTOP-003", "Lenovo ThinkPad", "Computers", "Lenovo", "ThinkPad X1", "SN-LN003", "Floor 3", "faulty", None),
]

for asset_id, name, category_name, brand, model, serial, location, status, owner_email in sample_assets:
    owner = StaffMember.objects.filter(email=owner_email).first() if owner_email else None
    asset, created = Asset.objects.get_or_create(
        asset_id=asset_id,
        defaults={
            "name": name,
            "category": categories.get(category_name),
            "brand": brand,
            "model": model,
            "serial_number": serial,
            "location": location,
            "status": status,
            "assigned_to": owner,
            "created_by": admin_user,
        },
    )
    if created:
        AssetHistory.objects.create(
            asset=asset,
            changed_by=admin_user,
            change_type="Registered",
            new_value="Asset created via seed",
        )

print(f"Created {len(sample_assets)} sample assets")
