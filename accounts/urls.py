from django.urls import path
from .views import profile, update_avatar, security

urlpatterns = [
    path("profile/", profile, name="account-profile"),
    path("avatar/", update_avatar, name="update-avatar"),
    path("security/", security, name="account-security"),
]
