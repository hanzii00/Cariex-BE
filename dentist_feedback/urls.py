# DentistFeedback/urls.py

from django.urls import path
from . import views

app_name = 'feedback'

urlpatterns = [
    # Feedback CRUD
    path('submit/<int:diagnosis_id>/', views.submit_feedback, name='submit'),
    path('get/<int:diagnosis_id>/', views.get_feedback, name='get'),
    path('update/<int:feedback_id>/', views.update_feedback, name='update'),
    path('delete/<int:feedback_id>/', views.delete_feedback, name='delete'),
    
    # Comments
    path('comment/<int:feedback_id>/', views.add_comment, name='add_comment'),
    
    # Dashboard & Analytics
    path('pending/', views.pending_validations, name='pending'),
    path('statistics/', views.feedback_statistics, name='statistics'),
    path('dashboard/', views.dentist_dashboard, name='dashboard'),
]