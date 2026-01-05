from rest_framework import serializers
from .models import DentistProfile


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    member_since = serializers.SerializerMethodField()

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
            "member_since",
            "updated_at",
        ]
        read_only_fields = ["updated_at", "member_since"]

    def get_member_since(self, obj):
        return obj.user.date_joined.year


class AvatarUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = DentistProfile
        fields = ["avatar_url"]


class AccountSecuritySerializer(serializers.Serializer):
    email = serializers.EmailField()
    is_verified = serializers.BooleanField()
    is_active = serializers.BooleanField()
    last_login = serializers.DateTimeField(allow_null=True)
    password_updated_at = serializers.DateTimeField(allow_null=True)
