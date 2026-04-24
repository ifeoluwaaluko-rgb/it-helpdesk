import os

from django import forms

from .models import Article


ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx", ".xlsx", ".xls", ".ppt", ".pptx", ".txt", ".csv", ".zip"
}
MAX_ATTACHMENT_SIZE = 15 * 1024 * 1024


def validate_knowledge_attachments(files):
    for uploaded in files:
        ext = os.path.splitext(uploaded.name)[1].lower()
        if uploaded.size > MAX_ATTACHMENT_SIZE:
            raise forms.ValidationError(f"{uploaded.name}: attachment must be 15 MB or smaller.")
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            raise forms.ValidationError(f"{uploaded.name}: attachment type is not allowed.")


class ArticleBaseForm(forms.Form):
    title = forms.CharField(max_length=255)
    content = forms.CharField(widget=forms.HiddenInput)
    category = forms.ChoiceField(choices=Article.CATEGORY_CHOICES, required=False)
    tags = forms.CharField(required=False, max_length=255)

    def clean_title(self):
        value = self.cleaned_data["title"].strip()
        if len(value) < 5:
            raise forms.ValidationError("Article title must be at least 5 characters long.")
        return value

    def clean_content(self):
        value = self.cleaned_data["content"].strip()
        if len(value) < 10:
            raise forms.ValidationError("Article content must be at least 10 characters long.")
        return value

    def clean_category(self):
        value = self.cleaned_data.get("category") or "other"
        valid = {choice for choice, _ in Article.CATEGORY_CHOICES}
        return value if value in valid else "other"

    def clean_tags(self):
        return self.cleaned_data["tags"].strip()


class ArticleCreateForm(ArticleBaseForm):
    source_ticket = forms.IntegerField(required=False)


class ArticleEditForm(ArticleBaseForm):
    revision_note = forms.CharField(required=False, max_length=255)
    delete_attachments = forms.MultipleChoiceField(required=False)

    def __init__(self, *args, attachments=None, **kwargs):
        super().__init__(*args, **kwargs)
        attachments = attachments or []
        self.fields["delete_attachments"].choices = [
            (str(att.pk), att.filename) for att in attachments
        ]

    def clean_revision_note(self):
        return self.cleaned_data["revision_note"].strip()
