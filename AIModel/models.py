from django.db import models
from django.conf import settings

class DiagnosisResult(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    image = models.ImageField(upload_to='dental_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Detection results
    has_caries = models.BooleanField(default=False)
    severity = models.CharField(max_length=50, blank=True)
    confidence_score = models.FloatField(null=True)
    
    # Bounding boxes (stored as JSON)
    lesion_boxes = models.JSONField(null=True, blank=True)
    
    # Processing status
    status = models.CharField(max_length=20, default='pending')  # pending, processing, completed
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Diagnosis {self.id} - {self.severity}"