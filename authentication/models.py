from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid

class User(AbstractUser):
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    
    reset_token = models.UUIDField(null=True, blank=True)
    reset_token_created = models.DateTimeField(null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def __str__(self):
        return self.email
    
    def create_reset_token(self):
        """Generate a new password reset token"""
        self.reset_token = uuid.uuid4()
        self.reset_token_created = timezone.now()
        self.save()
        return self.reset_token
    
    def is_reset_token_valid(self):
        """Check if reset token is still valid (24 hours)"""
        if not self.reset_token_created:
            return False
        time_elapsed = timezone.now() - self.reset_token_created
        return time_elapsed.total_seconds() < 86400  # 24 hours