from django.http import JsonResponse
from django.conf import settings
import cv2
import traceback
from pathlib import Path
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server
import matplotlib.pyplot as plt

from ..models import DiagnosisResult
from ..model_loader import model_loader
from ..xai_visualizer import XAIVisualizer


def explain_diagnosis(request, diagnosis_id):
    """
    Generate comprehensive XAI explanation for a diagnosis
    Returns multiple visualization techniques and conditional interpretation
    """
    try:
        print(f"[DEBUG] Starting explain_diagnosis for ID: {diagnosis_id}")
        
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        print(f"[DEBUG] Found diagnosis: {diagnosis}")
        
        # Load original image
        image_path = diagnosis.image.path
        print(f"[DEBUG] Loading image from: {image_path}")
        
        original_image = cv2.imread(image_path)
        
        if original_image is None:
            return JsonResponse({
                'success': False,
                'error': f'Could not read image at {image_path}'
            }, status=500)
        
        original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
        print(f"[DEBUG] Image loaded, shape: {original_image.shape}")
        
        # Preprocess and predict
        print("[DEBUG] Preprocessing image...")
        preprocessed = model_loader.preprocess_image(original_image)
        
        print("[DEBUG] Running prediction...")
        predictions = model_loader.predict(preprocessed)
        
        print("[DEBUG] Classifying severity...")
        severity_result = model_loader.classify_severity(predictions)
        print(f"[DEBUG] Severity result: {severity_result}")
        
        # Extract metrics
        affected_pct = severity_result.get('affected_percentage', 0)
        max_prob = severity_result.get('max_probability', 0)
        mean_prob = severity_result.get('mean_probability', 0)
        
        # Determine if caries detected
        has_caries = affected_pct > 0.1 or max_prob > 0.1
        print(f"[DEBUG] Has caries: {has_caries}")
        
        # Initialize XAI visualizer
        print("[DEBUG] Loading model for XAI...")
        model = model_loader.load_model()
        if model is None:
            return JsonResponse({
                'success': False,
                'error': 'Model could not be loaded'
            }, status=500)
            
        xai = XAIVisualizer(model)
        print("[DEBUG] XAI visualizer initialized")
        
        # Generate comprehensive explanation
        print("[DEBUG] Creating explanation report...")
        fig = xai.create_explanation_report(
            original_image=original_image,
            preprocessed_image=preprocessed,
            segmentation_mask=predictions,
            severity_result=severity_result
        )
        print("[DEBUG] Report created")
        
        # Save visualization
        output_dir = Path(image_path).parent
        output_filename = f'xai_explanation_{diagnosis_id}.png'
        output_path = output_dir / output_filename
        
        print(f"[DEBUG] Saving to: {output_path}")
        xai.save_explanation(fig, output_path)
        
        # Close figure to free memory (import matplotlib.pyplot as plt first)
        try:
            import matplotlib.pyplot as plt
            plt.close(fig)
        except Exception as close_error:
            print(f"[WARNING] Could not close figure: {close_error}")
        
        print("[DEBUG] Figure saved and closed")
        
        # Generate URL for the saved image
        explanation_url = f"{settings.MEDIA_URL}dental_images/{output_filename}"
        
        # Conditional interpretation based on detection
        if has_caries:
            interpretation = {
                'status': 'Caries Detected',
                'red_areas': 'Suspected caries regions requiring clinical review',
                'brightness': 'Confidence level (brighter = higher confidence)',
                'gradcam': 'Shows which regions influenced the AI decision most',
                'recommendation': 'Review red-highlighted areas during clinical examination'
            }
        else:
            interpretation = {
                'status': 'No Caries Detected',
                'red_areas': 'No significant caries regions detected',
                'brightness': 'All confidence values below detection threshold',
                'gradcam': 'Model found no significant areas of concern',
                'recommendation': 'Routine monitoring recommended, no immediate intervention needed'
            }
        
        print("[DEBUG] Returning success response")
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'explanation_url': explanation_url,
            'severity': severity_result.get('severity'),
            'confidence': float(severity_result.get('confidence', 0)),
            'affected_percentage': float(affected_pct),
            'mean_probability': float(mean_prob),
            'max_probability': float(max_prob),
            'has_caries': bool(has_caries),  # Convert to Python bool
            'techniques_used': [
                'Segmentation Heatmap',
                'Grad-CAM',
                'Probability Overlay',
                'Binary Thresholding',
                'Statistical Analysis'
            ],
            'interpretation': interpretation
        })
        
    except DiagnosisResult.DoesNotExist:
        print(f"[ERROR] Diagnosis {diagnosis_id} not found")
        return JsonResponse({
            'success': False,
            'error': f'Diagnosis with id {diagnosis_id} not found'
        }, status=404)
        
    except Exception as e:
        print(f"[ERROR] Exception in explain_diagnosis: {str(e)}")
        print(f"[ERROR] Traceback:\n{traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


def quick_xai_overlay(request, diagnosis_id):
    """
    Quick XAI endpoint - returns just the overlay image
    Faster for real-time visualization
    Provides conditional description based on detection
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
        severity_result = model_loader.classify_severity(predictions)
        
        # Check if caries detected
        affected_pct = severity_result.get('affected_percentage', 0)
        max_prob = severity_result.get('max_probability', 0)
        has_caries = affected_pct > 0.1 or max_prob > 0.1
        
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
        
        # Conditional description
        if has_caries:
            description = f'Red areas indicate suspected caries ({affected_pct:.2f}% affected)'
        else:
            description = 'No caries detected - original X-ray shows healthy tissue'
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'overlay_url': overlay_url,
            'has_caries': bool(has_caries),  # Convert to Python bool
            'affected_percentage': float(affected_pct),
            'description': description
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
    """
    Generate Grad-CAM visualization for a diagnosis
    Shows which regions the model focused on during prediction
    """
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        
        # Load image
        image_path = diagnosis.image.path
        original_image = cv2.imread(image_path)
        original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
        
        # Preprocess
        preprocessed = model_loader.preprocess_image(original_image)
        predictions = model_loader.predict(preprocessed)
        severity_result = model_loader.classify_severity(predictions)
        
        # Check detection status
        affected_pct = severity_result.get('affected_percentage', 0)
        has_caries = affected_pct > 0.1
        
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
        
        # Conditional description
        if has_caries:
            description = 'Heatmap showing which regions influenced the caries detection (brighter = more influential)'
        else:
            description = 'Heatmap showing model analysis - no significant areas of concern identified'
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'gradcam_url': gradcam_url,
            'has_caries': bool(has_caries),  # Convert to Python bool
            'description': description
        })
        
    except Exception as e:
        print(f"Error in get_gradcam: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)