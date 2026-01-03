from django.http import JsonResponse
from django.conf import settings
import cv2
import traceback
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ..models import DiagnosisResult
from ..model_loader import model_loader
from ..xai_visualizer import XAIVisualizer


def explain_diagnosis(request, diagnosis_id):
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        image_path = diagnosis.image.path
        original_image = cv2.imread(image_path)

        if original_image is None:
            return JsonResponse({'success': False, 'error': f'Could not read image at {image_path}'}, status=500)

        original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
        preprocessed = model_loader.preprocess_image(original_image)
        predictions = model_loader.predict(preprocessed)
        severity_result = model_loader.classify_severity(predictions)

        affected_pct = severity_result.get('affected_percentage', 0)
        max_prob = severity_result.get('max_probability', 0)
        mean_prob = severity_result.get('mean_probability', 0)
        has_caries = affected_pct > 0.1 or max_prob > 0.1

        model = model_loader.load_model()
        if model is None:
            return JsonResponse({'success': False, 'error': 'Model could not be loaded'}, status=500)

        xai = XAIVisualizer(model)
        fig = xai.create_explanation_report(
            original_image=original_image,
            preprocessed_image=preprocessed,
            segmentation_mask=predictions,
            severity_result=severity_result
        )

        output_dir = Path(image_path).parent
        output_filename = f'xai_explanation_{diagnosis_id}.png'
        output_path = output_dir / output_filename
        xai.save_explanation(fig, output_path)

        plt.close(fig)

        explanation_url = f"{settings.MEDIA_URL}dental_images/{output_filename}"

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

        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'explanation_url': explanation_url,
            'severity': severity_result.get('severity'),
            'confidence': float(severity_result.get('confidence', 0)),
            'affected_percentage': float(affected_pct),
            'mean_probability': float(mean_prob),
            'max_probability': float(max_prob),
            'has_caries': bool(has_caries),
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
        return JsonResponse({'success': False, 'error': f'Diagnosis with id {diagnosis_id} not found'}, status=404)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e), 'traceback': traceback.format_exc()}, status=500)


def quick_xai_overlay(request, diagnosis_id):
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        image_path = diagnosis.image.path
        original_image = cv2.imread(image_path)

        if original_image is None:
            return JsonResponse({'success': False, 'error': f'Could not read image at {image_path}'}, status=500)

        original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
        preprocessed = model_loader.preprocess_image(original_image)
        predictions = model_loader.predict(preprocessed)
        severity_result = model_loader.classify_severity(predictions)

        affected_pct = severity_result.get('affected_percentage', 0)
        max_prob = severity_result.get('max_probability', 0)
        has_caries = affected_pct > 0.1 or max_prob > 0.1

        xai = XAIVisualizer(model_loader.load_model())
        overlay, _ = xai.visualize_segmentation_overlay(original_image, predictions)

        output_dir = Path(image_path).parent
        output_filename = f'xai_quick_{diagnosis_id}.png'
        output_path = output_dir / output_filename
        cv2.imwrite(str(output_path), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))

        overlay_url = f"{settings.MEDIA_URL}dental_images/{output_filename}"
        description = (
            f'Red areas indicate suspected caries ({affected_pct:.2f}% affected)'
            if has_caries
            else 'No caries detected - original X-ray shows healthy tissue'
        )

        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'overlay_url': overlay_url,
            'has_caries': bool(has_caries),
            'affected_percentage': float(affected_pct),
            'description': description
        })

    except DiagnosisResult.DoesNotExist:
        return JsonResponse({'success': False, 'error': f'Diagnosis with id {diagnosis_id} not found'}, status=404)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def get_gradcam(request, diagnosis_id):
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
        image_path = diagnosis.image.path
        original_image = cv2.imread(image_path)
        original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)

        preprocessed = model_loader.preprocess_image(original_image)
        predictions = model_loader.predict(preprocessed)
        severity_result = model_loader.classify_severity(predictions)

        affected_pct = severity_result.get('affected_percentage', 0)
        has_caries = affected_pct > 0.1

        xai = XAIVisualizer(model_loader.load_model())
        gradcam = xai.generate_gradcam(preprocessed)
        gradcam_overlay = xai.overlay_heatmap(gradcam, original_image)

        output_dir = Path(image_path).parent
        output_filename = f'gradcam_{diagnosis_id}.png'
        output_path = output_dir / output_filename
        cv2.imwrite(str(output_path), cv2.cvtColor(gradcam_overlay, cv2.COLOR_RGB2BGR))

        gradcam_url = f"{settings.MEDIA_URL}dental_images/{output_filename}"
        description = (
            'Heatmap showing which regions influenced the caries detection (brighter = more influential)'
            if has_caries
            else 'Heatmap showing model analysis - no significant areas of concern identified'
        )

        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'gradcam_url': gradcam_url,
            'has_caries': bool(has_caries),
            'description': description
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
