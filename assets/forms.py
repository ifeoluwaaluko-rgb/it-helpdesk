import csv
import io

from django import forms

from tickets.models import Ticket

from .models import Asset, HardwareIncident


class AssetCreateForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = [
            "asset_id",
            "name",
            "category",
            "brand",
            "model",
            "serial_number",
            "location",
            "notes",
            "status",
            "assigned_to",
        ]

    def clean_asset_id(self):
        value = self.cleaned_data["asset_id"].strip().upper()
        if len(value) < 3:
            raise forms.ValidationError("Asset ID must be at least 3 characters long.")
        return value

    def clean_name(self):
        value = self.cleaned_data["name"].strip()
        if len(value) < 3:
            raise forms.ValidationError("Asset name must be at least 3 characters long.")
        return value


class AssetImportForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if not uploaded.name.lower().endswith(".csv"):
            raise forms.ValidationError("Please upload a CSV file.")
        try:
            decoded = uploaded.read().decode("utf-8", errors="replace")
            uploaded.seek(0)
            reader = csv.DictReader(io.StringIO(decoded))
            headers = set(reader.fieldnames or [])
        except Exception as exc:
            raise forms.ValidationError(f"Could not read CSV file: {exc}")

        required = {"asset_id", "name"}
        missing = required - headers
        if missing:
            raise forms.ValidationError(f"CSV is missing required columns: {', '.join(sorted(missing))}.")
        return uploaded


class AssetAssignmentForm(forms.Form):
    staff_id = forms.IntegerField(required=False, min_value=1)


class AssetStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Asset.STATUS_CHOICES)


class HardwareIncidentForm(forms.Form):
    title = forms.CharField(max_length=255)
    severity = forms.ChoiceField(choices=HardwareIncident.SEVERITY_CHOICES)
    description = forms.CharField(widget=forms.Textarea, required=False)
    ticket_id = forms.IntegerField(required=False, min_value=1)

    def __init__(self, *args, valid_ticket_ids=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.valid_ticket_ids = {int(ticket_id) for ticket_id in (valid_ticket_ids or [])}

    def clean_title(self):
        value = self.cleaned_data["title"].strip()
        if len(value) < 5:
            raise forms.ValidationError("Incident title must be at least 5 characters long.")
        return value

    def clean_description(self):
        return self.cleaned_data["description"].strip()

    def clean_ticket_id(self):
        ticket_id = self.cleaned_data.get("ticket_id")
        if ticket_id and ticket_id not in self.valid_ticket_ids:
            raise forms.ValidationError("Selected ticket is not available for incident linking.")
        return ticket_id
