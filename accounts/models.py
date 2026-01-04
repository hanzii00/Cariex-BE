from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class DentistProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    # Basic info
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    
    # Supabase Storage URL
    avatar_url = models.URLField(blank=True, null=True)

    # Professional
    education = models.TextField(blank=True)
    bio = models.TextField(blank=True)

    # Contact
    phone = models.CharField(max_length=30, blank=True)
    office_location = models.CharField(max_length=255, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} Profile"
