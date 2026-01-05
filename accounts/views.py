from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .serializers import (
    UserProfileSerializer,
    AvatarUploadSerializer,
    AccountSecuritySerializer
)


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def profile(request):
    """
    Get / Update user profile
    """
    profile = request.user.profile

    if request.method == "GET":
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    serializer = UserProfileSerializer(
        profile,
        data=request.data,
        partial=True
    )

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_avatar(request):
    """
    Save Supabase avatar URL
    """
    profile = request.user.profile
    avatar_url = request.data.get("avatar_url")

    if not avatar_url:
        return Response(
            {"error": "avatar_url is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    profile.avatar_url = avatar_url
    profile.save()

    return Response(
        {
            "message": "Avatar updated successfully",
            "avatar_url": avatar_url,
        },
        status=status.HTTP_200_OK
    )



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def security(request):
    """
    Read-only security/account status
    """
    user = request.user

    serializer = AccountSecuritySerializer({
        "email": user.email,
        "is_verified": user.is_verified,
        "is_active": user.is_active,
        "last_login": user.last_login,
        "last_password_change": user.last_password_change,
    })

    return Response(serializer.data, status=status.HTTP_200_OK)
