# DentistFeedback/models.py
# New separate Django app for feedback system

from django.db import models
from django.conf import settings


class ValidationStatus(models.Model):
    """
    Extended validation tracking for DiagnosisResult
    Separate table to avoid modifying AIModel
    """
    diagnosis = models.OneToOneField(
        'AIModel.DiagnosisResult',
        on_delete=models.CASCADE,
        related_name='validation_info',
        primary_key=True
    )
    
    validation_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Review'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('corrected', 'Corrected'),
        ],
        default='pending'
    )
    
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validations_performed'
    )
    
    validated_at = models.DateTimeField(null=True, blank=True)
    
    # Additional tracking
    validation_priority = models.IntegerField(
        default=0,
        help_text="Higher number = higher priority for review"
    )
    
    is_flagged = models.BooleanField(
        default=False,
        help_text="Flag for urgent review"
    )
    
    flag_reason = models.TextField(blank=True)
    
    class Meta:
        db_table = 'dentist_feedback_validation_status'
        verbose_name = 'Validation Status'
        verbose_name_plural = 'Validation Statuses'
    
    def __str__(self):
        return f"Validation for Diagnosis {self.diagnosis.id} - {self.validation_status}"


class DentistFeedback(models.Model):
    """
    Detailed feedback from dentists on AI predictions
    Completely independent from AIModel
    """
    diagnosis = models.ForeignKey(
        'AIModel.DiagnosisResult',
        on_delete=models.CASCADE,
        related_name='dentist_feedbacks'
    )
    
    dentist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='feedback_submissions'
    )
    
    # Validation decision
    is_correct = models.BooleanField(
        help_text="Is the AI prediction correct?"
    )
    
    # Corrected values (if AI was wrong)
    corrected_has_caries = models.BooleanField(null=True, blank=True)
    
    corrected_severity = models.CharField(
        max_length=50,
        choices=[
            ('Normal', 'Normal'),
            ('Mild', 'Mild'),
            ('Moderate', 'Moderate'),
            ('Severe', 'Severe'),
        ],
        null=True,
        blank=True
    )
    
    # Detailed feedback
    feedback_text = models.TextField(
        blank=True,
        help_text="Additional comments or observations"
    )
    
    # Bounding box corrections (JSON)
    corrected_boxes = models.JSONField(
        null=True,
        blank=True,
        help_text="Corrected or additional bounding boxes"
    )
    
    # Rating of AI performance (1-5)
    ai_performance_rating = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        null=True,
        blank=True,
        help_text="Rate AI accuracy (1=Poor, 5=Excellent)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Clinical notes
    clinical_findings = models.TextField(
        blank=True,
        help_text="Clinical examination findings"
    )
    
    recommended_treatment = models.TextField(
        blank=True,
        help_text="Recommended treatment plan"
    )
    
    # Confidence in feedback
    confidence_level = models.CharField(
        max_length=20,
        choices=[
            ('high', 'High Confidence'),
            ('medium', 'Medium Confidence'),
            ('low', 'Low Confidence - Needs Second Opinion'),
        ],
        default='high'
    )
    
    # Review status
    is_reviewed = models.BooleanField(
        default=False,
        help_text="Has this feedback been reviewed by senior dentist?"
    )
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feedback_reviews'
    )
    
    class Meta:
        db_table = 'dentist_feedback'
        ordering = ['-created_at']
        verbose_name = 'Dentist Feedback'
        verbose_name_plural = 'Dentist Feedbacks'
        indexes = [
            models.Index(fields=['diagnosis', '-created_at']),
            models.Index(fields=['dentist', '-created_at']),
            models.Index(fields=['is_correct']),
        ]
    
    def __str__(self):
        return f"Feedback by {self.dentist.username} on Diagnosis {self.diagnosis.id}"


class FeedbackCategory(models.Model):
    """
    Categorize types of feedback for analysis
    """
    feedback = models.ForeignKey(
        DentistFeedback,
        on_delete=models.CASCADE,
        related_name='categories'
    )
    
    category = models.CharField(
        max_length=50,
        choices=[
            ('false_positive', 'False Positive'),
            ('false_negative', 'False Negative'),
            ('severity_mismatch', 'Severity Mismatch'),
            ('location_inaccurate', 'Location Inaccurate'),
            ('excellent_detection', 'Excellent Detection'),
            ('image_quality_issue', 'Image Quality Issue'),
            ('artifact_detected', 'Artifact Detected as Caries'),
            ('other', 'Other'),
        ]
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'dentist_feedback_category'
        verbose_name_plural = 'Feedback Categories'
    
    def __str__(self):
        return f"{self.category} - Feedback {self.feedback.id}"


class FeedbackComment(models.Model):
    """
    Discussion thread for feedback
    Allows multiple dentists to discuss a case
    """
    feedback = models.ForeignKey(
        DentistFeedback,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='feedback_comments'
    )
    
    comment_text = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    # Optional: Reply to another comment
    parent_comment = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    class Meta:
        db_table = 'dentist_feedback_comment'
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.author.username} on Feedback {self.feedback.id}"


class FeedbackAttachment(models.Model):
    """
    Attachments for feedback (additional images, documents)
    """
    feedback = models.ForeignKey(
        DentistFeedback,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    
    file = models.FileField(upload_to='feedback_attachments/')
    
    file_type = models.CharField(
        max_length=20,
        choices=[
            ('image', 'Image'),
            ('pdf', 'PDF Document'),
            ('other', 'Other'),
        ],
        default='image'
    )
    
    description = models.CharField(max_length=255, blank=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'dentist_feedback_attachment'
    
    def __str__(self):
        return f"Attachment for Feedback {self.feedback.id}"


class ModelPerformanceMetric(models.Model):
    """
    Track model performance over time
    Aggregate statistics for analytics
    """
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    # Time period for these metrics
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Aggregate metrics
    total_diagnoses = models.IntegerField(default=0)
    total_feedback = models.IntegerField(default=0)
    correct_predictions = models.IntegerField(default=0)
    
    accuracy = models.FloatField(default=0.0)
    precision = models.FloatField(default=0.0)
    recall = models.FloatField(default=0.0)
    f1_score = models.FloatField(default=0.0)
    
    average_rating = models.FloatField(default=0.0)
    
    # Severity-specific accuracy (JSON)
    severity_metrics = models.JSONField(default=dict)
    
    # Category breakdown (JSON)
    category_breakdown = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'dentist_feedback_performance_metric'
        ordering = ['-calculated_at']
        indexes = [
            models.Index(fields=['-calculated_at']),
            models.Index(fields=['period_start', 'period_end']),
        ]
    
    def __str__(self):
        return f"Metrics for {self.period_start.date()} to {self.period_end.date()}"