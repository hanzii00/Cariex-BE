from django.db import models
from django.conf import settings
from dashboard.models import Patient

class DiagnosisResult(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('preprocessing', 'Preprocessing'),
        ('preprocessed', 'Preprocessed'),
        ('detecting', 'Detecting'),
        ('detected', 'Detected'),
        ('classifying', 'Classifying'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    # Dentist / uploader
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    # PATIENT LINK
    patient = models.ForeignKey(
        Patient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Supabase image URL
    image_url = models.URLField(
        blank=True,
        null=True
    )
    
    # Local image field (optional, for local storage)
    image = models.ImageField(upload_to='dental_images/', blank=True, null=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # AI results
    has_caries = models.BooleanField(default=False)
    severity = models.CharField(max_length=50, blank=True)
    confidence_score = models.FloatField(null=True)

    lesion_boxes = models.JSONField(null=True, blank=True)

    # Processing state
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # Error tracking
    error_message = models.TextField(blank=True, null=True)

    # Dentist validation
    verified_by_dentist = models.BooleanField(default=False)
    dentist_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        patient_name = self.patient.full_name if self.patient else "Unknown"
        return f"Diagnosis {self.id} - {patient_name}"