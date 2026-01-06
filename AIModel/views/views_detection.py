from django.http import JsonResponse
import cv2
import traceback

from ..models import DiagnosisResult
from ..model_loader import model_loader


def detect_caries(request, diagnosis_id):
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        diagnosis.status = 'detecting'
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
        
        bounding_boxes = []
        if 'segmentation_mask' in severity_result:
            bounding_boxes = model_loader.generate_bounding_boxes(
                severity_result['segmentation_mask'],
                threshold=0.5,
                min_area=50  
            )
        
        has_caries = severity_result['severity'].lower() not in ['normal', 'class_0']
        diagnosis.lesion_boxes = bounding_boxes
        diagnosis.has_caries = has_caries
        diagnosis.status = 'detected'
        diagnosis.save()
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'has_caries': has_caries,
            'bounding_boxes': bounding_boxes,
            'num_lesions': len(bounding_boxes),
            'affected_percentage': severity_result.get('affected_percentage', 0),
            'next_stage': 'classification'
        })
        
    except DiagnosisResult.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': f'Diagnosis with id {diagnosis_id} not found'
        }, status=404)
        
    except Exception as e:
        print(f"Error in detect_caries: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)