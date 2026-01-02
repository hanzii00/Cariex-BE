"""
AIModel/urls.py
URL configuration for dental caries detection system
"""

from django.urls import path
from . import views

app_name = 'AIModel'

urlpatterns = [
    path('upload/', views.upload_image, name='upload'),
    path('preprocess/<int:diagnosis_id>/', views.preprocess_image, name='preprocess'),
    path('detect/<int:diagnosis_id>/', views.detect_caries, name='detect'),
    path('classify/<int:diagnosis_id>/', views.classify_severity, name='classify'),
    path('results/<int:diagnosis_id>/', views.show_results, name='results'),
    path('api/diagnosis/<int:diagnosis_id>/', views.get_diagnosis_json, name='diagnosis_json'),
    
    path('explain/<int:diagnosis_id>/', views.explain_diagnosis, name='explain'),
    path('explain/quick/<int:diagnosis_id>/', views.quick_xai_overlay, name='quick_overlay'),
]