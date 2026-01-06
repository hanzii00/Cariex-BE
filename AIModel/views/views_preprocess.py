from django.http import JsonResponse
import cv2
import traceback

from ..models import DiagnosisResult
from ..model_loader import model_loader
import time


def preprocess_image(request, diagnosis_id):
    try:
        start = time.time()
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        diagnosis.status = 'preprocessing'
        diagnosis.save()
        image_path = diagnosis.image.path
        image = cv2.imread(image_path)
        
        if image is None:
            return JsonResponse({
                'success': False, 
                'error': f'Could not read image at {image_path}'
            }, status=500)
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        t0 = time.time()
        preprocessed = model_loader.preprocess_image(image_rgb)
        t1 = time.time()
        diagnosis.status = 'preprocessed'
        diagnosis.save()
        total = time.time() - start
        print(f"Preprocess: read+prep took {t1 - t0:.3f}s, total {total:.3f}s for diagnosis {diagnosis_id}")
        
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