from django.views.decorators.http import require_http_methods
from django.core.serializers import serialize
from django.http import JsonResponse
from ..models import DiagnosisResult
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes  # ✅ Add this
from rest_framework.permissions import IsAuthenticated  # ✅ Add this
from rest_framework.response import Response  # ✅ Add this
from rest_framework import status  # ✅ Add this
import cv2
import numpy as np
import traceback

from ..models import DiagnosisResult
from ..model_loader import model_loader

@api_view(['GET'])  # ✅ Use DRF decorator instead of @require_http_methods
@permission_classes([IsAuthenticated])
def get_all_diagnoses(request):
    """Return all diagnosis records for the authenticated user's patients"""
    try:
        # ✅ Filter by logged-in dentist's patients
        diagnoses = DiagnosisResult.objects.filter(
            patient__isnull=False,  # Only scans with a patient
            patient__created_by=request.user  # Only YOUR patients
        )
        
        results = []
        for diagnosis in diagnoses:
            results.append({
                'id': diagnosis.id,
                'patient_id': diagnosis.patient.id,
                'patient_name': diagnosis.patient.full_name,
                'image_url': diagnosis.image_url or (diagnosis.image.url if diagnosis.image else None),
                'uploaded_at': diagnosis.uploaded_at.isoformat(),
                'has_caries': diagnosis.has_caries,
                'severity': diagnosis.severity,
                'confidence_score': diagnosis.confidence_score,
                'lesion_boxes': diagnosis.lesion_boxes,
                'status': diagnosis.status,
            })

        return Response({
            'success': True,
            'count': len(results),
            'results': results
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@require_http_methods(["GET"])
def get_single_diagnosis(request, diagnosis_id):
    """Return a single diagnosis record by ID"""
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        data = {
            'id': diagnosis.id,
            'patient_id': diagnosis.patient.id if diagnosis.patient else None,
            'patient_name': diagnosis.patient.full_name if diagnosis.patient else None,
            'image_url': diagnosis.image_url or (diagnosis.image.url if diagnosis.image else None),
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
