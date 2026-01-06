from django.http import JsonResponse
from django.conf import settings
import cv2
import traceback
from pathlib import Path
import urllib.request
import numpy as np
import os
import io
import uuid
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ..models import DiagnosisResult
from ..model_loader import model_loader
from ..xai_visualizer import XAIVisualizer
from ..supabase import supabase


def _load_image_and_output_dir(diagnosis: DiagnosisResult):
    """Load image either from local file or from Supabase URL.

    Returns (original_image_rgb, output_dir) or (None, error_msg).
    """
    media_root = getattr(settings, "MEDIA_ROOT", None)

    # Prefer local file if available
    if diagnosis.image and getattr(diagnosis.image, "name", None):
        try:
            image_path = diagnosis.image.path
            original_image = cv2.imread(image_path)
            if original_image is None:
                return None, f"Could not read image at {image_path}"
            original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
            output_dir = Path(image_path).parent
            return original_image, output_dir
        except Exception as e:
            # Fall back to URL below
            print("XAI: error reading local image, falling back to URL:", e)

    # Fallback: load from Supabase/public URL
    if diagnosis.image_url:
        try:
            with urllib.request.urlopen(diagnosis.image_url) as resp:
                data = resp.read()
            nparr = np.frombuffer(data, np.uint8)
            original_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if original_image is None:
                return None, f"Could not decode image from URL {diagnosis.image_url}"
            original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)

            # Save XAI outputs under MEDIA_ROOT/dental_images
            if media_root:
                output_dir = Path(media_root) / "dental_images"
            else:
                output_dir = Path("media") / "dental_images"
            os.makedirs(output_dir, exist_ok=True)
            return original_image, output_dir
        except Exception as e:
            return None, f"Error fetching image from URL: {e}"

    return None, "Diagnosis has no associated image file or URL"


def explain_diagnosis(request, diagnosis_id):
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)

        original_image, output_dir_or_error = _load_image_and_output_dir(diagnosis)
        if original_image is None:
            return JsonResponse({"success": False, "error": output_dir_or_error}, status=500)

        output_dir = output_dir_or_error
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
            severity_result=severity_result,
        )

        # Save locally (optional cache)
        output_filename = f'xai_explanation_{diagnosis_id}.png'
        output_path = output_dir / output_filename
        xai.save_explanation(fig, output_path)

        # Also upload to Supabase so the XAI image is stored with other images
        supa_path = f"xai/{diagnosis_id}/xai_explanation_{diagnosis_id}.png"
        try:
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            # Use upsert so repeated calls do not error with 409 Duplicate
            # Supabase expects header values as strings, not bools
            supabase.storage.from_("images").upload(
                supa_path,
                buf.getvalue(),
                {"content-type": "image/png", "upsert": "true"},
            )
            explanation_url = supabase.storage.from_("images").get_public_url(supa_path)
        except Exception as e:
            # If upload fails (e.g. duplicate), try to reuse any existing Supabase file
            print("XAI Supabase upload error (explanation):", e)
            try:
                explanation_url = supabase.storage.from_("images").get_public_url(supa_path)
            except Exception:
                # Fallback to local MEDIA_URL if Supabase is unavailable
                explanation_url = f"{settings.MEDIA_URL}dental_images/{output_filename}"

        plt.close(fig)

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
        original_image, output_dir_or_error = _load_image_and_output_dir(diagnosis)
        if original_image is None:
            return JsonResponse({"success": False, "error": output_dir_or_error}, status=500)

        output_dir = output_dir_or_error
        preprocessed = model_loader.preprocess_image(original_image)
        predictions = model_loader.predict(preprocessed)
        severity_result = model_loader.classify_severity(predictions)

        affected_pct = severity_result.get('affected_percentage', 0)
        max_prob = severity_result.get('max_probability', 0)
        has_caries = affected_pct > 0.1 or max_prob > 0.1

        xai = XAIVisualizer(model_loader.load_model())
        overlay, _ = xai.visualize_segmentation_overlay(original_image, predictions)
        output_filename = f'xai_quick_{diagnosis_id}.png'
        output_path = output_dir / output_filename
        cv2.imwrite(str(output_path), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))

        # Upload quick overlay PNG to Supabase
        supa_path = f"xai/{diagnosis_id}/xai_quick_{diagnosis_id}.png"
        try:
            success, png_arr = cv2.imencode('.png', cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
            if not success:
                raise RuntimeError('Failed to encode quick overlay PNG')
            # Use upsert so repeated calls do not error with 409 Duplicate
            # Supabase expects header values as strings, not bools
            supabase.storage.from_("images").upload(
                supa_path,
                png_arr.tobytes(),
                {"content-type": "image/png", "upsert": "true"},
            )
            overlay_url = supabase.storage.from_("images").get_public_url(supa_path)
        except Exception as e:
            print("XAI Supabase upload error (quick overlay):", e)
            try:
                overlay_url = supabase.storage.from_("images").get_public_url(supa_path)
            except Exception:
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
        original_image, output_dir_or_error = _load_image_and_output_dir(diagnosis)
        if original_image is None:
            return JsonResponse({"success": False, "error": output_dir_or_error}, status=500)

        output_dir = output_dir_or_error

        preprocessed = model_loader.preprocess_image(original_image)
        predictions = model_loader.predict(preprocessed)
        severity_result = model_loader.classify_severity(predictions)

        affected_pct = severity_result.get('affected_percentage', 0)
        has_caries = affected_pct > 0.1

        xai = XAIVisualizer(model_loader.load_model())
        gradcam = xai.generate_gradcam(preprocessed)
        gradcam_overlay = xai.overlay_heatmap(gradcam, original_image)
        output_filename = f'gradcam_{diagnosis_id}.png'
        output_path = output_dir / output_filename
        cv2.imwrite(str(output_path), cv2.cvtColor(gradcam_overlay, cv2.COLOR_RGB2BGR))

        # Upload Grad-CAM overlay PNG to Supabase
        supa_path = f"xai/{diagnosis_id}/gradcam_{diagnosis_id}.png"
        try:
            success, png_arr = cv2.imencode('.png', cv2.cvtColor(gradcam_overlay, cv2.COLOR_RGB2BGR))
            if not success:
                raise RuntimeError('Failed to encode Grad-CAM PNG')
            # Use upsert so repeated calls do not error with 409 Duplicate
            # Supabase expects header values as strings, not bools
            supabase.storage.from_("images").upload(
                supa_path,
                png_arr.tobytes(),
                {"content-type": "image/png", "upsert": "true"},
            )
            gradcam_url = supabase.storage.from_("images").get_public_url(supa_path)
        except Exception as e:
            print("XAI Supabase upload error (gradcam):", e)
            try:
                gradcam_url = supabase.storage.from_("images").get_public_url(supa_path)
            except Exception:
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
