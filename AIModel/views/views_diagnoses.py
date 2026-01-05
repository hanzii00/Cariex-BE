from django.views.decorators.http import require_http_methods
from django.core.serializers import serialize
from django.http import JsonResponse
from ..models import DiagnosisResult


@require_http_methods(["GET"])
def get_all_diagnoses(request):
    """Return all diagnosis records"""
    try:
        diagnoses = DiagnosisResult.objects.all().values(
            'id', 'user', 'image', 'uploaded_at', 'has_caries',
            'severity', 'confidence_score', 'lesion_boxes', 'status'
        )
        return JsonResponse({
            'success': True,
            'count': diagnoses.count(),
            'results': list(diagnoses)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_single_diagnosis(request, diagnosis_id):
    """Return a single diagnosis record by ID"""
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        data = {
            'id': diagnosis.id,
            'user': diagnosis.user.id if diagnosis.user else None,
            'image_url': diagnosis.image.url,
            'uploaded_at': diagnosis.uploaded_at.isoformat(),
            'has_caries': diagnosis.has_caries,
            'severity': diagnosis.severity,
            'confidence_score': diagnosis.confidence_score,
            'lesion_boxes': diagnosis.lesion_boxes,
            'status': diagnosis.status
        }
        return JsonResponse({'success': True, 'data': data})
    except DiagnosisResult.DoesNotExist:
        return JsonResponse({'success': False, 'error': f'Diagnosis with id {diagnosis_id} not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_http_methods(["DELETE"])
def delete_diagnosis(request, diagnosis_id):
    """Delete a diagnosis record"""
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        diagnosis.delete()
        return JsonResponse({'success': True, 'message': f'Diagnosis {diagnosis_id} deleted successfully'})
    except DiagnosisResult.DoesNotExist:
        return JsonResponse({'success': False, 'error': f'Diagnosis with id {diagnosis_id} not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
