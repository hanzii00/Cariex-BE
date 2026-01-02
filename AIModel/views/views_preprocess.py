from django.http import JsonResponse
import cv2
import traceback

from ..models import DiagnosisResult
from ..model_loader import model_loader


def preprocess_image(request, diagnosis_id):
    """
    F5: Preprocessing Engine
    Preprocesses uploaded image for model input
    Supports both GET and POST for testing
    """
    try:
        # Fetch diagnosis record
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        diagnosis.status = 'preprocessing'
        diagnosis.save()
        
        # Read image from storage
        image_path = diagnosis.image.path
        image = cv2.imread(image_path)
        
        if image is None:
            return JsonResponse({
                'success': False, 
                'error': f'Could not read image at {image_path}'
            }, status=500)
        
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Preprocess image using model loader
        preprocessed = model_loader.preprocess_image(image_rgb)
        
        # Update status
        diagnosis.status = 'preprocessed'
        diagnosis.save()
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'status': 'preprocessed',
            'preprocessed_shape': list(preprocessed.shape),
            'next_stage': 'detection'
        })
        
    except DiagnosisResult.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': f'Diagnosis with id {diagnosis_id} not found'
        }, status=404)
        
    except Exception as e:
        print(f"Error in preprocess: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)