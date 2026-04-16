from django.contrib import admin
from .models import Ticket, TicketComment, Profile, CannedResponse, EscalationRule

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user','role']

class CommentInline(admin.TabularInline):
    model = TicketComment; extra = 0

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['id','title','status','priority','category','channel','assigned_to','created_at']
    list_filter = ['status','priority','category','channel']
    search_fields = ['title','description','user_email']
    inlines = [CommentInline]

@admin.register(CannedResponse)
class CannedResponseAdmin(admin.ModelAdmin):
    list_display = ['title','category']

@admin.register(EscalationRule)
class EscalationRuleAdmin(admin.ModelAdmin):
    list_display = ['name','priority','hours_without_update','escalate_to_role','is_active']
