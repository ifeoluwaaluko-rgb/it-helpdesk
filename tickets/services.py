from dataclasses import dataclass

from django.contrib.auth.models import User
from django.utils import timezone

from .models import Ticket, TicketComment, TicketEditHistory
from .notifications import notify_assignment, notify_status_change


@dataclass
class TicketActionResult:
    changed: bool = False
    message: str = ""
    level: str = "success"


def mark_first_response(ticket):
    if not ticket.first_response_at:
        ticket.first_response_at = timezone.now()
        ticket.save(update_fields=["first_response_at", "updated_at"])


def add_comment(ticket, author, body):
    body = (body or "").strip()
    if not body:
        return TicketActionResult(changed=False)
    TicketComment.objects.create(ticket=ticket, author=author, body=body)
    mark_first_response(ticket)
    return TicketActionResult(changed=True)


def pickup_ticket(ticket, user):
    if ticket.assigned_to:
        return TicketActionResult(changed=False)
    ticket.assigned_to = user
    ticket.status = "in_progress"
    ticket.save()
    mark_first_response(ticket)
    notify_assignment(ticket, user)
    return TicketActionResult(changed=True, message=f"You picked up ticket #{ticket.id}.")


def update_ticket_status(ticket, user, new_status):
    valid_statuses = {status for status, _ in Ticket.STATUS_CHOICES}
    if new_status not in valid_statuses:
        return TicketActionResult(changed=False)

    old_status = ticket.status
    ticket.status = new_status
    update_fields = ["status", "updated_at"]
    if new_status == "resolved" and not ticket.resolved_at:
        ticket.resolved_at = timezone.now()
        update_fields.append("resolved_at")
    ticket.save(update_fields=update_fields)

    if new_status in {"in_progress", "pending", "resolved", "closed"}:
        mark_first_response(ticket)
    if new_status != old_status:
        notify_status_change(ticket, user)
        return TicketActionResult(changed=True)
    return TicketActionResult(changed=False)


def reassign_ticket(ticket, user_id):
    if not user_id:
        return TicketActionResult(changed=False)

    old_assignee = ticket.assigned_to
    ticket.assigned_to = User.objects.get(pk=int(user_id))
    ticket.save(update_fields=["assigned_to", "updated_at"])
    if ticket.assigned_to and (not old_assignee or old_assignee.id != ticket.assigned_to.id):
        notify_assignment(ticket, ticket.assigned_to)
        mark_first_response(ticket)
        return TicketActionResult(changed=True)
    return TicketActionResult(changed=False)


def snapshot_ticket_edit(ticket, edited_by, note):
    TicketEditHistory.objects.create(
        ticket=ticket,
        edited_by=edited_by,
        title=ticket.title,
        description=ticket.description,
        category=ticket.category,
        subcategory=ticket.subcategory,
        item=ticket.item,
        priority=ticket.priority,
        status=ticket.status,
        edit_note=note,
    )


def update_ticket_category(ticket, edited_by, category, subcategory, item):
    snapshot_ticket_edit(ticket, edited_by, "Category updated")
    ticket.category = category or ticket.category
    ticket.subcategory = subcategory or ""
    ticket.item = item or ""
    ticket.save(update_fields=["category", "subcategory", "item", "updated_at"])
    return TicketActionResult(changed=True, message="Category updated.")


def update_ticket_fields(ticket, edited_by, payload, can_edit_status):
    snapshot_ticket_edit(ticket, edited_by, payload.get("edit_note") or "Edited")

    valid_priorities = {priority for priority, _ in Ticket.PRIORITY_CHOICES}
    valid_statuses = {status for status, _ in Ticket.STATUS_CHOICES}
    valid_categories = {category for category, _ in Ticket.CATEGORY_CHOICES}

    ticket.title = (payload.get("title") or ticket.title).strip() or ticket.title
    ticket.description = (payload.get("description") or ticket.description).strip() or ticket.description

    new_category = payload.get("category", ticket.category)
    ticket.category = new_category if new_category in valid_categories else ticket.category
    ticket.subcategory = payload.get("subcategory", "")
    ticket.item = payload.get("item", "")

    new_priority = payload.get("priority", ticket.priority)
    ticket.priority = new_priority if new_priority in valid_priorities else ticket.priority
    ticket.request_type = payload.get('request_type') or ticket.request_type
    ticket.impact = payload.get('impact') or ticket.impact
    ticket.urgency = payload.get('urgency') or ticket.urgency
    ticket.approval_status = payload.get('approval_status') or ticket.approval_status
    ticket.business_service = payload.get('business_service', ticket.business_service)
    ticket.tags = payload.get("tags", ticket.tags)

    if can_edit_status:
        new_status = payload.get("status", ticket.status)
        ticket.status = new_status if new_status in valid_statuses else ticket.status
        if ticket.status == "resolved" and not ticket.resolved_at:
            ticket.resolved_at = timezone.now()

    ticket.save()
    return TicketActionResult(changed=True, message=f"Ticket #{ticket.id} updated.")
