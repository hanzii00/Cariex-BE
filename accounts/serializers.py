from rest_framework import serializers
from .models import DentistProfile


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = DentistProfile
        fields = [
            "email",
            "first_name",
            "last_name",
            "avatar_url",
            "education",
            "bio",
            "phone",
            "office_location",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]


class AvatarUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = DentistProfile
        fields = ["avatar"]


class AccountSecuritySerializer(serializers.Serializer):
    email = serializers.EmailField()
    is_verified = serializers.BooleanField()
    is_active = serializers.BooleanField()
    last_login = serializers.DateTimeField()
    last_password_change = serializers.DateTimeField(allow_null=True)
