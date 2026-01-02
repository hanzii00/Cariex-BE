"""
AIModel/views/__init__.py
Central import file for all view modules
Makes all views accessible via 'from AIModel import views'
"""

# Use relative imports (with dot notation) since we're inside a package
from .views_upload import upload_image
from .views_preprocess import preprocess_image
from .views_detection import detect_caries
from .views_classification import classify_severity
from .views_results import show_results, get_diagnosis_json
from .views_xai import explain_diagnosis, quick_xai_overlay, get_gradcam

# Define what's available when someone does 'from views import *'
__all__ = [
    'upload_image',
    'preprocess_image',
    'detect_caries',
    'classify_severity',
    'show_results',
    'get_diagnosis_json',
    'explain_diagnosis',
    'quick_xai_overlay',
    'get_gradcam',
]