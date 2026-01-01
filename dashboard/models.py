from django.db import models
from django.conf import settings
from django.utils import timezone

class Patient(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='patients'
    )
    
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    
    blood_type = models.CharField(max_length=5, blank=True)
    allergies = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_visit = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['created_by']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self):
        today = timezone.now().date()
        age = today.year - self.date_of_birth.year
        if today.month < self.date_of_birth.month or (
            today.month == self.date_of_birth.month and 
            today.day < self.date_of_birth.day
        ):
            age -= 1
        return age


class Record(models.Model):
    RECORD_TYPES = [
        ('consultation', 'Consultation'),
        ('diagnosis', 'Diagnosis'),
        ('prescription', 'Prescription'),
        ('lab_result', 'Lab Result'),
        ('imaging', 'Imaging'),
        ('vaccination', 'Vaccination'),
        ('procedure', 'Procedure'),
        ('other', 'Other'),
    ]
    
    patient = models.ForeignKey(
        Patient, 
        on_delete=models.CASCADE,
        related_name='records'
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='created_records'
    )
    
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    diagnosis = models.TextField(blank=True)
    prescription = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    visit_date = models.DateTimeField(default=timezone.now)
    follow_up_date = models.DateField(null=True, blank=True)
    
    attachments = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-visit_date']
        indexes = [
            models.Index(fields=['patient', '-visit_date']),
            models.Index(fields=['record_type']),
        ]
    
    def __str__(self):
        return f"{self.patient.full_name} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.pk: 
            self.patient.last_visit = self.visit_date
            self.patient.save()
        super().save(*args, **kwargs)