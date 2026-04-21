"""
API endpoint for testing Groq teeth position detection
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import traceback
import json

from ..groq_api import detect_teeth_position, detect_teeth_position_text
from ..models import DiagnosisResult


@csrf_exempt
def detect_teeth_position_endpoint(request, diagnosis_id=None):
    """
    Detect teeth position for a diagnosis image using Groq API.
    Can be called with POST request containing image path or diagnosis_id.
    
    POST parameters:
    - diagnosis_id: ID of existing diagnosis to analyze
    - image_path: Direct path to image file (alternative to diagnosis_id)
    - description: Text description of the image (alternative to image_path)
    """
    try:
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'POST only'}, status=405)
        
        # Parse request body
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = request.POST
        
        # Get image path from diagnosis_id or direct path or description
        image_path = None
        
        if diagnosis_id:
            try:
                diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
                image_path = diagnosis.image.path
            except DiagnosisResult.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Diagnosis with id {diagnosis_id} not found'
                }, status=404)
        elif 'image_path' in data:
            image_path = data['image_path']
        elif 'description' in data:
            # Use text-based detection
            result = detect_teeth_position_text(data['description'])
            return JsonResponse(result)
        else:
            return JsonResponse({
                'success': False,
                'error': 'Either diagnosis_id, image_path, or description is required'
            }, status=400)
        
        # Detect teeth position
        result = detect_teeth_position(image_path)
        return JsonResponse(result)
        
    except Exception as e:
        print(f"Error in detect_teeth_position_endpoint: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def get_teeth_position_info(request, diagnosis_id):
    """
    Get teeth position information for a specific diagnosis.
    
    GET endpoint that returns the stored teeth position info.
    """
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'teeth_position': diagnosis.teeth_position,
            'teeth_position_confidence': diagnosis.teeth_position_confidence,
            'has_caries': diagnosis.has_caries,
            'severity': diagnosis.severity
        })
    except DiagnosisResult.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Diagnosis with id {diagnosis_id} not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
