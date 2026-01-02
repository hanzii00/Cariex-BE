from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse

from ..models import DiagnosisResult


def show_results(request, diagnosis_id):
    """
    Display diagnosis results with visualizations
    Shows severity, confidence, and bounding boxes
    """
    diagnosis = get_object_or_404(DiagnosisResult, id=diagnosis_id)
    
    context = {
        'diagnosis': diagnosis,
        'severity': diagnosis.severity,
        'confidence': diagnosis.confidence_score,
        'bounding_boxes': diagnosis.lesion_boxes,
        'image_url': diagnosis.image.url,
        'has_caries': diagnosis.has_caries,
        'num_lesions': len(diagnosis.lesion_boxes) if diagnosis.lesion_boxes else 0
    }
    
    return render(request, 'AIModel/results.html', context)


def get_diagnosis_json(request, diagnosis_id):
    """
    API endpoint to get diagnosis results as JSON
    Useful for AJAX requests or mobile apps
    """
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis.id,
            'image_url': diagnosis.image.url,
            'uploaded_at': diagnosis.uploaded_at.isoformat(),
            'has_caries': diagnosis.has_caries,
            'severity': diagnosis.severity,
            'confidence_score': diagnosis.confidence_score,
            'bounding_boxes': diagnosis.lesion_boxes,
            'status': diagnosis.status
        })
        
    except DiagnosisResult.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Diagnosis with id {diagnosis_id} not found'
        }, status=404)