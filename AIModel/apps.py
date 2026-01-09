import os
from django.apps import AppConfig


class AimodelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'AIModel'

    def ready(self):
        # Preload ML model only when explicitly enabled.
        # Avoid loading in CI or environments where TensorFlow isn't available.
        preload_env = os.getenv('PRELOAD_AI_MODEL', 'false').lower()
        ci_env = os.getenv('CI', '').lower()

        should_preload = preload_env in ('1', 'true', 'yes') and ci_env not in ('1', 'true', 'yes')

        if not should_preload:
            return

        try:
            from .model_loader import model_loader
            model_loader.load_model()
            print('AIModel: pretrained model loaded on startup')
        except Exception as e:
            print('AIModel: error preloading model:', e)