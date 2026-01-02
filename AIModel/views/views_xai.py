from django.http import JsonResponse
from django.conf import settings
import cv2
import traceback
from pathlib import Path

from ..models import DiagnosisResult
from ..model_loader import model_loader
from ..xai_visualizer import XAIVisualizer


def explain_diagnosis(request, diagnosis_id):

    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        
        # Load original image
        image_path = diagnosis.image.path
        original_image = cv2.imread(image_path)
        
        if original_image is None:
            return JsonResponse({
                'success': False,
                'error': f'Could not read image at {image_path}'
            }, status=500)
        
        original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
        
        # Preprocess and predict
        preprocessed = model_loader.preprocess_image(original_image)
        predictions = model_loader.predict(preprocessed)
        severity_result = model_loader.classify_severity(predictions)
        
        # Initialize XAI visualizer
        xai = XAIVisualizer(model_loader.load_model())
        
        # Generate comprehensive explanation
        fig = xai.create_explanation_report(
            original_image=original_image,
            preprocessed_image=preprocessed,
            segmentation_mask=predictions,
            severity_result=severity_result
        )
        
        # Save visualization
        output_dir = Path(image_path).parent
        output_filename = f'xai_explanation_{diagnosis_id}.png'
        output_path = output_dir / output_filename
        
        xai.save_explanation(fig, output_path)
        
        # Generate URL for the saved image
        explanation_url = f"{settings.MEDIA_URL}dental_images/{output_filename}"
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'explanation_url': explanation_url,
            'severity': severity_result.get('severity'),
            'confidence': float(severity_result.get('confidence', 0)),
            'affected_percentage': float(severity_result.get('affected_percentage', 0)),
            'techniques_used': [
                'Segmentation Heatmap',
                'Grad-CAM',
                'Probability Overlay',
                'Binary Thresholding',
                'Statistical Analysis'
            ],
            'interpretation': {
                'red_areas': 'Suspected caries regions',
                'green_areas': 'Healthy tissue',
                'brightness': 'Confidence level (brighter = higher confidence)',
                'gradcam': 'Shows which regions influenced the AI decision most'
            }
        })
        
    except DiagnosisResult.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Diagnosis with id {diagnosis_id} not found'
        }, status=404)
        
    except Exception as e:
        print(f"Error in explain_diagnosis: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def quick_xai_overlay(request, diagnosis_id):
    """
    Quick XAI endpoint - returns just the overlay image
    Faster for real-time visualization
    Overlays red (caries) and green (healthy) colors on original image
    """
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        
        # Load image
        image_path = diagnosis.image.path
        original_image = cv2.imread(image_path)
        
        if original_image is None:
            return JsonResponse({
                'success': False,
                'error': f'Could not read image at {image_path}'
            }, status=500)
        
        original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
        
        # Get predictions
        preprocessed = model_loader.preprocess_image(original_image)
        predictions = model_loader.predict(preprocessed)
        
        # Create XAI visualizer
        xai = XAIVisualizer(model_loader.load_model())
        
        # Generate overlay only
        overlay, _ = xai.visualize_segmentation_overlay(original_image, predictions)
        
        # Save quick overlay
        output_dir = Path(image_path).parent
        output_filename = f'xai_quick_{diagnosis_id}.png'
        output_path = output_dir / output_filename
        
        cv2.imwrite(str(output_path), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
        
        overlay_url = f"{settings.MEDIA_URL}dental_images/{output_filename}"
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'overlay_url': overlay_url,
            'description': 'Red areas indicate suspected caries, green areas indicate healthy tissue'
        })
        
    except DiagnosisResult.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Diagnosis with id {diagnosis_id} not found'
        }, status=404)
        
    except Exception as e:
        print(f"Error in quick_xai_overlay: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def get_gradcam(request, diagnosis_id):
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        
        # Load image
        image_path = diagnosis.image.path
        original_image = cv2.imread(image_path)
        original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
        
        # Preprocess
        preprocessed = model_loader.preprocess_image(original_image)
        
        # Create XAI visualizer
        xai = XAIVisualizer(model_loader.load_model())
        
        # Generate Grad-CAM
        gradcam = xai.generate_gradcam(preprocessed)
        gradcam_overlay = xai.overlay_heatmap(gradcam, original_image)
        
        # Save
        output_dir = Path(image_path).parent
        output_filename = f'gradcam_{diagnosis_id}.png'
        output_path = output_dir / output_filename
        
        cv2.imwrite(str(output_path), cv2.cvtColor(gradcam_overlay, cv2.COLOR_RGB2BGR))
        
        gradcam_url = f"{settings.MEDIA_URL}dental_images/{output_filename}"
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'gradcam_url': gradcam_url,
            'description': 'Heatmap showing which regions influenced the AI decision'
        })
        
    except Exception as e:
        print(f"Error in get_gradcam: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)