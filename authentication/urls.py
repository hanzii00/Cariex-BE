from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('verify/<uuid:token>/', views.verify_email, name='verify_email'),
    path('profile/', views.profile, name='profile'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/<uuid:token>/', views.password_reset_verify, name='password_reset_verify'),
]