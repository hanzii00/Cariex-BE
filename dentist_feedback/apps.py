from django.apps import AppConfig

class DentistFeedbackConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dentist_feedback'
    verbose_name = 'Dentist Feedback & Validation System'
    
    def ready(self):
        """
        Import signals or perform startup tasks here
        """
        pass