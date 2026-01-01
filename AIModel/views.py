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
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        diagnosis.status = 'preprocessing'
        diagnosis.save()
        
        # Read image
        image_path = diagnosis.image.path
        image = cv2.imread(image_path)
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
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def detect_caries(request, diagnosis_id):
    """F6: Caries Detection AI"""
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        diagnosis.status = 'detecting'
        diagnosis.save()
        
        # Read and preprocess image
        image_path = diagnosis.image.path
        image = cv2.imread(image_path)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        preprocessed = model_loader.preprocess_image(image_rgb)
        
        # Run detection
        predictions = model_loader.predict(preprocessed)
        
        # Generate bounding boxes (if your model supports object detection)
        # This depends on your model architecture
        bounding_boxes = generate_bounding_boxes(predictions, image.shape)
        
        diagnosis.lesion_boxes = bounding_boxes
        diagnosis.has_caries = len(bounding_boxes) > 0
        diagnosis.status = 'detected'
        diagnosis.save()
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'has_caries': diagnosis.has_caries,
            'bounding_boxes': bounding_boxes,
            'next_stage': 'classification'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def classify_severity(request, diagnosis_id):
    """F6: Severity Classification AI"""
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        diagnosis.status = 'classifying'
        diagnosis.save()
        
        # Read and preprocess image
        image_path = diagnosis.image.path
        image = cv2.imread(image_path)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        preprocessed = model_loader.preprocess_image(image_rgb)
        
        # Run prediction
        predictions = model_loader.predict(preprocessed)
        
        # Classify severity
        severity_result = model_loader.classify_severity(predictions)
        
        diagnosis.severity = severity_result['severity']
        diagnosis.confidence_score = severity_result['confidence']
        diagnosis.status = 'completed'
        diagnosis.save()
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'severity': severity_result['severity'],
            'confidence': severity_result['confidence'],
            'probabilities': severity_result['all_probabilities']
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

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