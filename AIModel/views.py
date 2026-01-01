from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
import cv2
import numpy as np
from PIL import Image
import io

from .model_loader import model_loader
from .models import DiagnosisResult

def upload_image(request):
    """F4: Dental Image Upload & Acquisition"""
    if request.method == 'POST' and request.FILES.get('image'):
        image_file = request.FILES['image']
        
        # Save to database
        diagnosis = DiagnosisResult.objects.create(
            user=request.user if request.user.is_authenticated else None,
            image=image_file,
            status='uploaded'
        )
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis.id,
            'message': 'Image uploaded successfully',
            'preview_url': diagnosis.image.url
        })
    
    return render(request, 'AIModel/upload.html')

def preprocess_image(request, diagnosis_id):
    """F5: Preprocessing Engine"""
    # Allow both GET and POST for easier testing
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        diagnosis.status = 'preprocessing'
        diagnosis.save()
        
        # Read image
        image_path = diagnosis.image.path
        image = cv2.imread(image_path)
        
        if image is None:
            return JsonResponse({
                'success': False, 
                'error': f'Could not read image at {image_path}'
            }, status=500)
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Preprocess
        preprocessed = model_loader.preprocess_image(image_rgb)
        
        # Store preprocessed data temporarily (or pass to next stage)
        diagnosis.status = 'preprocessed'
        diagnosis.save()
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'status': 'preprocessed',
            'next_stage': 'detection'
        })
        
    except DiagnosisResult.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': f'Diagnosis with id {diagnosis_id} not found'
        }, status=404)
    except Exception as e:
        import traceback
        print(f"Error in preprocess: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)

def detect_caries(request, diagnosis_id):
    """F6: Caries Detection AI"""
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        diagnosis.status = 'detecting'
        diagnosis.save()
        
        # Read and preprocess image
        image_path = diagnosis.image.path
        image = cv2.imread(image_path)
        
        if image is None:
            return JsonResponse({
                'success': False, 
                'error': f'Could not read image at {image_path}'
            }, status=500)
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        preprocessed = model_loader.preprocess_image(image_rgb)
        
        # Run detection
        predictions = model_loader.predict(preprocessed)
        
        # Classify severity (this now handles segmentation output)
        severity_result = model_loader.classify_severity(predictions)
        
        # Generate bounding boxes from segmentation mask
        bounding_boxes = []
        if 'segmentation_mask' in severity_result:
            bounding_boxes = model_loader.generate_bounding_boxes(
                severity_result['segmentation_mask'],
                threshold=0.5,
                min_area=50  # Minimum area in pixels
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
            'affected_percentage': severity_result.get('affected_percentage', 0),
            'next_stage': 'classification'
        })
        
    except DiagnosisResult.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'error': f'Diagnosis with id {diagnosis_id} not found'
        }, status=404)
    except Exception as e:
        import traceback
        print(f"Error in detect_caries: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)
def classify_severity(request, diagnosis_id):
    """F6: Severity Classification AI"""
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        diagnosis.status = 'classifying'
        diagnosis.save()
        
        # Read and preprocess image
        image_path = diagnosis.image.path
        image = cv2.imread(image_path)
        
        if image is None:
            return JsonResponse({
                'success': False, 
                'error': f'Could not read image at {image_path}'
            }, status=500)
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        preprocessed = model_loader.preprocess_image(image_rgb)
        
        # Run prediction
        predictions = model_loader.predict(preprocessed)
        
        # Classify severity
        severity_result = model_loader.classify_severity(predictions)
        
        # Remove segmentation_mask from result (too large for JSON)
        if 'segmentation_mask' in severity_result:
            del severity_result['segmentation_mask']
        
        # Convert all numpy types to Python native types for JSON serialization
        severity_result = {
            key: float(value) if isinstance(value, (np.floating, np.integer)) else value
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
        import traceback
        print(f"Error in classify_severity: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)

def show_results(request, diagnosis_id):
    """Result page with bounding boxes"""
    diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
    
    context = {
        'diagnosis': diagnosis,
        'severity': diagnosis.severity,
        'confidence': diagnosis.confidence_score,
        'bounding_boxes': diagnosis.lesion_boxes,
        'image_url': diagnosis.image.url
    }
    
    return render(request, 'AIModel/results.html', context)

def generate_bounding_boxes(predictions, image_shape):
    """Generate bounding boxes based on model predictions"""
    # This depends on your model's output format
    # Example for classification model (you may need to adapt)
    boxes = []
    
    # If your model outputs heatmaps or segmentation masks
    # you would process them here to generate boxes
    
    return boxes