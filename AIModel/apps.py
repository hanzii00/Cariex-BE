from django.apps import AppConfig

class AimodelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'AIModel'

    def ready(self):
        # Preload ML model to avoid first-request latency
        try:
            from .model_loader import model_loader
            model_loader.load_model()
            print('AIModel: pretrained model loaded on startup')
        except Exception as e:
            print('AIModel: error preloading model:', e)