"""
AIModel/urls.py
URL configuration for dental caries detection system
"""

from django.urls import path
from . import views

app_name = 'AIModel'

urlpatterns = [
    # existing routes...
    path('upload/', views.upload_image, name='upload'),
    path('preprocess/<int:diagnosis_id>/', views.preprocess_image, name='preprocess'),
    path('detect/<int:diagnosis_id>/', views.detect_caries, name='detect'),
    path('classify/<int:diagnosis_id>/', views.classify_severity, name='classify'),
    path('results/<int:diagnosis_id>/', views.show_results, name='results'),
    
    path('explain/<int:diagnosis_id>/', views.explain_diagnosis, name='explain'),
    path('explain/quick/<int:diagnosis_id>/', views.quick_xai_overlay, name='quick_overlay'),
    
    path('diagnosis/<int:diagnosis_id>/', views.get_diagnosis_json, name='diagnosis_json'),
    path('diagnosis/all/', views.get_all_diagnoses, name='get_all_diagnoses'),
    path('diagnosis/<int:diagnosis_id>/', views.get_single_diagnosis, name='get_single_diagnosis'),
    path('diagnosis/<int:diagnosis_id>/delete/', views.delete_diagnosis, name='delete_diagnosis'),
]
