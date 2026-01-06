from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from ..models import DiagnosisResult


def show_results(request, diagnosis_id):
    diagnosis = get_object_or_404(DiagnosisResult, id=diagnosis_id)
    
    return JsonResponse({
        'success': True,
        'diagnosis_id': diagnosis.id,
        'image_url': diagnosis.image_url or (diagnosis.image.url if diagnosis.image else None),
        'has_caries': diagnosis.has_caries,
        'severity': diagnosis.severity,
        'confidence_score': diagnosis.confidence_score,
        'bounding_boxes': diagnosis.lesion_boxes,
        'lesion_boxes': diagnosis.lesion_boxes,
        'num_lesions': len(diagnosis.lesion_boxes) if diagnosis.lesion_boxes else 0,
        'status': diagnosis.status,
        'uploaded_at': diagnosis.uploaded_at.isoformat(),
    })


def get_diagnosis_json(request, diagnosis_id):
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        data = {
            'id': diagnosis.id,
            'image_url': diagnosis.image_url or (diagnosis.image.url if diagnosis.image else None),
            'uploaded_at': diagnosis.uploaded_at.isoformat(),
            'has_caries': diagnosis.has_caries,
            'severity': diagnosis.severity,
            'confidence_score': diagnosis.confidence_score,
            'lesion_boxes': diagnosis.lesion_boxes,
            'bounding_boxes': diagnosis.lesion_boxes,
            'num_lesions': len(diagnosis.lesion_boxes) if diagnosis.lesion_boxes else 0,
            'status': diagnosis.status
        }
        return JsonResponse({'success': True, 'data': data})
        
    except DiagnosisResult.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Diagnosis with id {diagnosis_id} not found'
        }, status=404)
