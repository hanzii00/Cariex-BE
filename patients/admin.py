from django.contrib import admin
from .models import Patient, Record


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'age', 'gender', 'phone', 'created_by', 'last_visit', 'created_at']
    list_filter = ['gender', 'created_at', 'last_visit']
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    readonly_fields = ['created_at', 'updated_at', 'age']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('created_by', 'first_name', 'last_name', 'date_of_birth', 'gender')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone', 'address')
        }),
        ('Medical Information', {
            'fields': ('blood_type', 'allergies')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone')
        }),
        ('Metadata', {
            'fields': ('last_visit', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = ['title', 'patient', 'record_type', 'visit_date', 'created_by', 'created_at']
    list_filter = ['record_type', 'visit_date', 'created_at']
    search_fields = ['title', 'description', 'patient__first_name', 'patient__last_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('patient', 'created_by', 'record_type', 'title', 'description')
        }),
        ('Medical Details', {
            'fields': ('diagnosis', 'prescription', 'notes')
        }),
        ('Visit Information', {
            'fields': ('visit_date', 'follow_up_date')
        }),
        ('Attachments', {
            'fields': ('attachments',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )