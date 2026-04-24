import os

from django import forms

from .models import ServiceCatalogItem, Ticket


ALLOWED_ATTACHMENT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".docx", ".xlsx", ".txt", ".zip"}
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024


class TicketCreateForm(forms.Form):
    title = forms.CharField(max_length=255)
    description = forms.CharField(widget=forms.Textarea)
    user_email = forms.EmailField()
    channel = forms.ChoiceField(choices=Ticket.CHANNEL_CHOICES, required=False)
    request_type = forms.ChoiceField(choices=Ticket.REQUEST_TYPE_CHOICES, required=False)
    impact = forms.ChoiceField(choices=Ticket.IMPACT_CHOICES, required=False)
    urgency = forms.ChoiceField(choices=Ticket.URGENCY_CHOICES, required=False)
    business_service = forms.CharField(required=False, max_length=120)
    catalog_item = forms.ModelChoiceField(queryset=ServiceCatalogItem.objects.filter(is_active=True), required=False)
    staff_member = forms.IntegerField(required=False)
    attachment = forms.FileField(required=False)

    def clean_title(self):
        value = self.cleaned_data["title"].strip()
        if len(value) < 5:
            raise forms.ValidationError("Subject must be at least 5 characters long.")
        return value

    def clean_description(self):
        value = self.cleaned_data["description"].strip()
        if len(value) < 10:
            raise forms.ValidationError("Description must be at least 10 characters long.")
        return value

    def clean_channel(self):
        value = self.cleaned_data.get("channel") or "manual"
        valid_channels = {choice for choice, _ in Ticket.CHANNEL_CHOICES}
        return value if value in valid_channels else "manual"

    def clean_request_type(self):
        value = self.cleaned_data.get('request_type') or 'incident'
        valid = {choice for choice, _ in Ticket.REQUEST_TYPE_CHOICES}
        return value if value in valid else 'incident'

    def clean_impact(self):
        value = self.cleaned_data.get('impact') or 'single_user'
        valid = {choice for choice, _ in Ticket.IMPACT_CHOICES}
        return value if value in valid else 'single_user'

    def clean_urgency(self):
        value = self.cleaned_data.get('urgency') or 'normal'
        valid = {choice for choice, _ in Ticket.URGENCY_CHOICES}
        return value if value in valid else 'normal'

    def clean_business_service(self):
        return self.cleaned_data.get('business_service', '').strip()

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if not attachment:
            return attachment
        ext = os.path.splitext(attachment.name)[1].lower()
        if attachment.size > MAX_ATTACHMENT_SIZE:
            raise forms.ValidationError("Attachment must be 10 MB or smaller.")
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            raise forms.ValidationError("Attachment type is not allowed.")
        return attachment


class TicketCommentForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea,
        error_messages={"required": "Comment cannot be empty."},
    )

    def clean_body(self):
        value = self.cleaned_data["body"].strip()
        if not value:
            raise forms.ValidationError("Comment cannot be empty.")
        return value


class TicketStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Ticket.STATUS_CHOICES)


class TicketCategoryUpdateForm(forms.Form):
    category = forms.ChoiceField(choices=Ticket.CATEGORY_CHOICES)
    subcategory = forms.CharField(required=False, max_length=100)
    item = forms.CharField(required=False, max_length=200)

    def clean_subcategory(self):
        return self.cleaned_data["subcategory"].strip()

    def clean_item(self):
        return self.cleaned_data["item"].strip()


class TicketReassignForm(forms.Form):
    user_id = forms.IntegerField(min_value=1)


class TicketEditForm(forms.Form):
    title = forms.CharField(max_length=255)
    description = forms.CharField(widget=forms.Textarea)
    category = forms.ChoiceField(choices=Ticket.CATEGORY_CHOICES)
    subcategory = forms.CharField(required=False, max_length=100)
    item = forms.CharField(required=False, max_length=200)
    priority = forms.ChoiceField(choices=Ticket.PRIORITY_CHOICES)
    request_type = forms.ChoiceField(choices=Ticket.REQUEST_TYPE_CHOICES, required=False)
    impact = forms.ChoiceField(choices=Ticket.IMPACT_CHOICES, required=False)
    urgency = forms.ChoiceField(choices=Ticket.URGENCY_CHOICES, required=False)
    approval_status = forms.ChoiceField(choices=Ticket.APPROVAL_CHOICES, required=False)
    business_service = forms.CharField(required=False, max_length=120)
    status = forms.ChoiceField(choices=Ticket.STATUS_CHOICES, required=False)
    tags = forms.CharField(required=False, max_length=255)
    edit_note = forms.CharField(required=False, max_length=255)

    def __init__(self, *args, ticket=None, can_edit_status=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticket = ticket
        self.can_edit_status = can_edit_status
        if not can_edit_status:
            self.fields.pop("status")

    def clean_title(self):
        value = self.cleaned_data["title"].strip()
        if len(value) < 5:
            raise forms.ValidationError("Title must be at least 5 characters long.")
        return value

    def clean_description(self):
        value = self.cleaned_data["description"].strip()
        if len(value) < 10:
            raise forms.ValidationError("Description must be at least 10 characters long.")
        return value

    def clean_subcategory(self):
        return self.cleaned_data["subcategory"].strip()

    def clean_item(self):
        return self.cleaned_data["item"].strip()

    def clean_business_service(self):
        return self.cleaned_data.get('business_service', '').strip()

    def clean_tags(self):
        return self.cleaned_data["tags"].strip()

    def clean_edit_note(self):
        return self.cleaned_data["edit_note"].strip()
