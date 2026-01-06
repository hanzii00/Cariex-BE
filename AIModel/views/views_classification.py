from django.http import JsonResponse
import cv2
import numpy as np
import traceback

from ..models import DiagnosisResult
from ..model_loader import model_loader


def classify_severity(request, diagnosis_id):
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        diagnosis.status = 'classifying'
        diagnosis.save()
        
        image_path = diagnosis.image.path
        image = cv2.imread(image_path)
        
        if image is None:
            return JsonResponse({
                'success': False, 
                'error': f'Could not read image at {image_path}'
            }, status=500)
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        preprocessed = model_loader.preprocess_image(image_rgb)
        
        predictions = model_loader.predict(preprocessed)
        
        severity_result = model_loader.classify_severity(predictions)
        
        if 'segmentation_mask' in severity_result:
            del severity_result['segmentation_mask']
        
        severity_result = {
            key: _convert_to_native_type(value)
            for key, value in severity_result.items()
        }
        
        diagnosis.severity = severity_result['severity']
        diagnosis.confidence_score = severity_result['confidence']
        diagnosis.status = 'completed'
        diagnosis.save()
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'severity': severity_result['severity'],
            'confidence': float(severity_result['confidence']),
            'probabilities': severity_result.get('all_probabilities', []),
            'affected_percentage': float(severity_result.get('affected_percentage', 0)),
            'mean_probability': float(severity_result.get('mean_probability', 0)),
            'max_probability': float(severity_result.get('max_probability', 0))
        })
        
    except DiagnosisResult.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': f'Diagnosis with id {diagnosis_id} not found'
        }, status=404)
        
    except Exception as e:
        print(f"Error in classify_severity: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


def _convert_to_native_type(value):
    if isinstance(value, (np.floating, np.integer)):
        return float(value)
    elif isinstance(value, np.ndarray):
        return value.tolist()
    elif isinstance(value, list):
        return [_convert_to_native_type(item) for item in value]
    return value