from django.contrib import admin
from .models import AssetCategory, Asset, AssetHistory, HardwareIncident

@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ['name','icon']

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['asset_id','name','category','assigned_to','status']
    list_filter = ['status','category']
    search_fields = ['asset_id','name','serial_number']

@admin.register(HardwareIncident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ['title','asset','severity','resolved','created_at']
    list_filter = ['severity','resolved']
