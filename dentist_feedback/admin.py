from django.contrib import admin
from django.utils.html import format_html
from .models import (
    ValidationStatus, DentistFeedback, FeedbackCategory,
    FeedbackComment, FeedbackAttachment, ModelPerformanceMetric
)


@admin.register(ValidationStatus)
class ValidationStatusAdmin(admin.ModelAdmin):
    list_display = [
        'diagnosis_id', 'validation_badge', 'validated_by',
        'validated_at', 'priority_badge', 'is_flagged'
    ]
    list_filter = ['validation_status', 'is_flagged', 'validated_at']
    search_fields = ['diagnosis__id', 'validated_by__username']
    readonly_fields = ['validated_at']
    
    fieldsets = (
        ('Diagnosis', {
            'fields': ('diagnosis',)
        }),
        ('Validation Info', {
            'fields': ('validation_status', 'validated_by', 'validated_at')
        }),
        ('Priority & Flags', {
            'fields': ('validation_priority', 'is_flagged', 'flag_reason')
        }),
    )
    
    def validation_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'approved': '#28a745',
            'rejected': '#dc3545',
            'corrected': '#17a2b8'
        }
        color = colors.get(obj.validation_status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.validation_status.upper()
        )
    validation_badge.short_description = "Status"
    
    def priority_badge(self, obj):
        if obj.validation_priority > 5:
            color = '#dc3545'
        elif obj.validation_priority > 0:
            color = '#ffc107'
        else:
            color = '#6c757d'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.validation_priority
        )
    priority_badge.short_description = "Priority"


class FeedbackCategoryInline(admin.TabularInline):
    model = FeedbackCategory
    extra = 1


class FeedbackCommentInline(admin.TabularInline):
    model = FeedbackComment
    extra = 0
    readonly_fields = ['author', 'created_at']


@admin.register(DentistFeedback)
class DentistFeedbackAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'diagnosis_link', 'dentist', 'correctness_badge',
        'confidence_badge', 'ai_performance_rating', 'created_at'
    ]
    list_filter = [
        'is_correct', 'confidence_level', 'ai_performance_rating',
        'is_reviewed', 'created_at'
    ]
    search_fields = ['dentist__username', 'diagnosis__id', 'feedback_text']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [FeedbackCategoryInline, FeedbackCommentInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('diagnosis', 'dentist', 'is_correct', 'confidence_level')
        }),
        ('Corrections', {
            'fields': ('corrected_has_caries', 'corrected_severity', 'corrected_boxes'),
            'classes': ('collapse',)
        }),
        ('Detailed Feedback', {
            'fields': ('feedback_text', 'ai_performance_rating')
        }),
        ('Clinical Information', {
            'fields': ('clinical_findings', 'recommended_treatment'),
            'classes': ('collapse',)
        }),
        ('Review Status', {
            'fields': ('is_reviewed', 'reviewed_by'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def diagnosis_link(self, obj):
        return format_html(
            '<a href="/admin/AIModel/diagnosisresult/{}/change/">Diagnosis #{}</a>',
            obj.diagnosis.id,
            obj.diagnosis.id
        )
    diagnosis_link.short_description = "Diagnosis"
    
    def correctness_badge(self, obj):
        if obj.is_correct:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✓ CORRECT</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px;">✗ INCORRECT</span>'
            )
    correctness_badge.short_description = "Correctness"
    
    def confidence_badge(self, obj):
        colors = {
            'high': '#28a745',
            'medium': '#ffc107',
            'low': '#dc3545'
        }
        color = colors.get(obj.confidence_level, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.confidence_level.upper()
        )
    confidence_badge.short_description = "Confidence"


@admin.register(FeedbackCategory)
class FeedbackCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'feedback_link', 'category_badge', 'notes_preview']
    list_filter = ['category']
    search_fields = ['feedback__id', 'notes']
    
    def feedback_link(self, obj):
        return format_html(
            '<a href="/admin/DentistFeedback/dentistfeedback/{}/change/">Feedback #{}</a>',
            obj.feedback.id,
            obj.feedback.id
        )
    feedback_link.short_description = "Feedback"
    
    def category_badge(self, obj):
        colors = {
            'false_positive': '#dc3545',
            'false_negative': '#dc3545',
            'severity_mismatch': '#ffc107',
            'location_inaccurate': '#ffc107',
            'excellent_detection': '#28a745',
        }
        color = colors.get(obj.category, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.category.replace('_', ' ').title()
        )
    category_badge.short_description = "Category"
    
    def notes_preview(self, obj):
        return obj.notes[:50] + '...' if len(obj.notes) > 50 else obj.notes
    notes_preview.short_description = "Notes"


@admin.register(FeedbackComment)
class FeedbackCommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'feedback_link', 'author', 'comment_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['author__username', 'comment_text']
    readonly_fields = ['created_at', 'updated_at']
    
    def feedback_link(self, obj):
        return format_html(
            '<a href="/admin/DentistFeedback/dentistfeedback/{}/change/">Feedback #{}</a>',
            obj.feedback.id,
            obj.feedback.id
        )
    feedback_link.short_description = "Feedback"
    
    def comment_preview(self, obj):
        return obj.comment_text[:80] + '...' if len(obj.comment_text) > 80 else obj.comment_text
    comment_preview.short_description = "Comment"


@admin.register(FeedbackAttachment)
class FeedbackAttachmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'feedback_link', 'file_type', 'description', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['feedback__id', 'description']
    readonly_fields = ['uploaded_at']
    
    def feedback_link(self, obj):
        return format_html(
            '<a href="/admin/DentistFeedback/dentistfeedback/{}/change/">Feedback #{}</a>',
            obj.feedback.id,
            obj.feedback.id
        )
    feedback_link.short_description = "Feedback"


@admin.register(ModelPerformanceMetric)
class ModelPerformanceMetricAdmin(admin.ModelAdmin):
    list_display = [
        'period_display', 'accuracy_badge', 'precision', 'recall',
        'f1_score', 'total_feedback', 'calculated_at'
    ]
    list_filter = ['calculated_at', 'period_start']
    readonly_fields = ['calculated_at']
    
    def period_display(self, obj):
        return f"{obj.period_start.date()} to {obj.period_end.date()}"
    period_display.short_description = "Period"
    
    def accuracy_badge(self, obj):
        if obj.accuracy >= 90:
            color = '#28a745'
        elif obj.accuracy >= 75:
            color = '#ffc107'
        else:
            color = '#dc3545'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{:.2f}%</span>',
            color,
            obj.accuracy
        )
    accuracy_badge.short_description = "Accuracy"