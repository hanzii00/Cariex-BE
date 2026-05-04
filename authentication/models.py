from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
import uuid


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    objects = UserManager()

    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False)

    reset_token = models.UUIDField(null=True, blank=True)
    reset_token_created = models.DateTimeField(null=True, blank=True)

    username = models.CharField(max_length=150, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email.split('@')[0]
        super().save(*args, **kwargs)

    def create_reset_token(self):
        self.reset_token = uuid.uuid4()
        self.reset_token_created = timezone.now()
        self.save()
        return self.reset_token

    def is_reset_token_valid(self):
        if not self.reset_token_created:
            return False
        time_elapsed = timezone.now() - self.reset_token_created
        return time_elapsed.total_seconds() < 86400