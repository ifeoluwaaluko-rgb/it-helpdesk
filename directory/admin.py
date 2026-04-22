from django.contrib import admin
from .models import Department, StaffMember

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name']

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ['full_name','email','department','job_title','is_active']
    list_filter = ['is_active','department']
    search_fields = ['first_name','last_name','email']
