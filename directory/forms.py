import csv
import io

from django import forms

from .models import StaffMember


class StaffMemberForm(forms.ModelForm):
    class Meta:
        model = StaffMember
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "department",
            "job_title",
            "is_active",
        ]

    def clean_first_name(self):
        value = self.cleaned_data["first_name"].strip()
        if len(value) < 2:
            raise forms.ValidationError("First name must be at least 2 characters long.")
        return value

    def clean_last_name(self):
        value = self.cleaned_data["last_name"].strip()
        if len(value) < 2:
            raise forms.ValidationError("Last name must be at least 2 characters long.")
        return value

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class StaffImportForm(forms.Form):
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

        required = {"first_name", "last_name", "email"}
        missing = required - headers
        if missing:
            raise forms.ValidationError(f"CSV is missing required columns: {', '.join(sorted(missing))}.")
        return uploaded
