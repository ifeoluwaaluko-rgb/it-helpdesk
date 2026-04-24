from django.contrib import admin
from .models import Ticket, TicketComment, Profile, CannedResponse, EscalationRule, ServiceCatalogItem

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user','role']

class CommentInline(admin.TabularInline):
    model = TicketComment; extra = 0

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['id','title','request_type','status','priority','impact','urgency','category','channel','assigned_to','created_at']
    list_filter = ['status','priority','category','channel']
    search_fields = ['title','description','user_email']
    inlines = [CommentInline]

@admin.register(CannedResponse)
class CannedResponseAdmin(admin.ModelAdmin):
    list_display = ['title','category']

@admin.register(EscalationRule)
class EscalationRuleAdmin(admin.ModelAdmin):
    list_display = ['name','priority','hours_without_update','escalate_to_role','is_active']


@admin.register(ServiceCatalogItem)
class ServiceCatalogItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'request_type', 'category', 'default_priority', 'approval_required', 'estimated_hours', 'is_active']
    list_filter = ['request_type', 'category', 'approval_required', 'is_active']
    search_fields = ['name', 'description', 'fulfillment_hint']
    prepopulated_fields = {'slug': ('name',)}
