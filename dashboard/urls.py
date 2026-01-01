from django.urls import path
from . import views

urlpatterns = [
    # Dashboard stats
    path('stats/', views.dashboard_stats, name='dashboard_stats'),
    
    # Patient endpoints
    path('patients/', views.patient_list_create, name='patient_list_create'),
    path('patients/<int:pk>/', views.patient_detail, name='patient_detail'),
    path('patients/<int:patient_id>/records/', views.patient_records, name='patient_records'),
    
    # Record endpoints
    path('records/', views.record_list_create, name='record_list_create'),
    path('records/<int:pk>/', views.record_detail, name='record_detail'),
]