from django.urls import path
from . import views

app_name = 'AIModel'

urlpatterns = [
    # F4: Upload
    path('upload/', views.upload_image, name='upload'),
    
    # F5: Preprocessing
    path('preprocess/<int:diagnosis_id>/', views.preprocess_image, name='preprocess'),
    
    # F6: Detection
    path('detect/<int:diagnosis_id>/', views.detect_caries, name='detect'),
    
    # F6: Classification
    path('classify/<int:diagnosis_id>/', views.classify_severity, name='classify'),
    
    # Results
    path('results/<int:diagnosis_id>/', views.show_results, name='results'),
]