from django.http import JsonResponse
from django.conf import settings
import traceback
from pathlib import Path
import urllib.request
import numpy as np
import os
import io

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAVE_MATPLOTLIB = True
except ImportError:
    matplotlib = None
    plt = None
    HAVE_MATPLOTLIB = False

from ..models import DiagnosisResult
from ..model_loader import model_loader
from ..xai_visualizer import XAIVisualizer
from ..supabase import supabase

try:
    import cv2
except Exception:
    cv2 = None


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _load_image_and_output_dir(diagnosis: DiagnosisResult):
    media_root = getattr(settings, "MEDIA_ROOT", None)

    if cv2 is None:
        return None, 'OpenCV (cv2) is not installed in this environment.'

    if diagnosis.image and getattr(diagnosis.image, "name", None):
        try:
            image_path     = diagnosis.image.path
            original_image = cv2.imread(image_path)
            if original_image is None:
                return None, f"Could not read image at {image_path}"
            original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
            return original_image, Path(image_path).parent
        except Exception as e:
            print("XAI: error reading local image, falling back to URL:", e)

    if diagnosis.image_url:
        try:
            with urllib.request.urlopen(diagnosis.image_url) as resp:
                data = resp.read()
            nparr          = np.frombuffer(data, np.uint8)
            original_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if original_image is None:
                return None, f"Could not decode image from URL {diagnosis.image_url}"
            original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
            output_dir = Path(media_root) / "dental_images" if media_root else Path("media") / "dental_images"
            os.makedirs(output_dir, exist_ok=True)
            return original_image, output_dir
        except Exception as e:
            return None, f"Error fetching image from URL: {e}"

    return None, "Diagnosis has no associated image file or URL"


def _upload_to_supabase(supa_path, png_bytes, fallback_url):
    try:
        supabase.storage.from_("images").upload(
            supa_path, png_bytes,
            {"content-type": "image/png", "upsert": "true"},
        )
        return supabase.storage.from_("images").get_public_url(supa_path)
    except Exception as e:
        print(f"XAI Supabase upload error ({supa_path}):", e)
        try:
            return supabase.storage.from_("images").get_public_url(supa_path)
        except Exception:
            return fallback_url


def _severity_result_from_db(diagnosis: DiagnosisResult) -> dict:
    """
    Build a severity_result dict from the values already stored on the
    DiagnosisResult row.  This guarantees that every XAI endpoint shows
    exactly the same confidence/severity as the Results tab, regardless of
    any non-determinism in a fresh model forward pass.

    Fields that don't exist on the model yet gracefully fall back to 0 / [].
    """
    return {
        'severity':           diagnosis.severity or 'N/A',
        'confidence':         float(getattr(diagnosis, 'confidence_score', 0) or 0),
        'affected_percentage': float(getattr(diagnosis, 'affected_percentage', 0) or 0),
        'mean_probability':   float(getattr(diagnosis, 'mean_probability', 0) or 0),
        'max_probability':    float(getattr(diagnosis, 'max_probability', 0) or 0),
        # Store as JSON list on the model if you want per-class bars;
        # falls back to empty list gracefully.
        'all_probabilities':  getattr(diagnosis, 'all_probabilities', []) or [],
    }


def _adaptive_has_caries(severity_result: dict, predictions: np.ndarray):
    """
    Derive has_caries / adaptive_affected from stored severity_result.

    For classification models the mask shape is (1, N) so we use severity.
    For segmentation models (1, H, W, 1) we re-threshold the predictions
    — the predictions tensor is still needed here because the DB only stores
    the scalar summary, not the full pixel mask.
    """
    if len(predictions.shape) == 2:
        severity     = severity_result.get('severity', 'Healthy')
        confidence   = float(severity_result.get('confidence', 0))
        has_caries   = severity.lower() != 'healthy'
        affected_pct = confidence if has_caries else 0.0
        return has_caries, affected_pct

    mask               = predictions[0, :, :, 0]
    adaptive_threshold = max(0.5 * float(np.max(mask)), 0.05)
    adaptive_affected  = float(np.sum(mask > adaptive_threshold) / mask.size * 100)
    return adaptive_affected > 1.0, adaptive_affected


# ──────────────────────────────────────────────────────────────────────────────
# Views
# ──────────────────────────────────────────────────────────────────────────────

def explain_diagnosis(request, diagnosis_id):
    if not HAVE_MATPLOTLIB:
        return JsonResponse({
            'success': False,
            'error': 'matplotlib is not installed. XAI explanation reports require matplotlib.'
        }, status=503)

    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)

        original_image, output_dir_or_error = _load_image_and_output_dir(diagnosis)
        if original_image is None:
            return JsonResponse({"success": False, "error": output_dir_or_error}, status=500)
        output_dir = output_dir_or_error

        # Run inference — still needed for Grad-CAM gradient tape and the
        # segmentation mask.  We do NOT use the returned severity_result for
        # the response; we pull those numbers from the DB instead.
        try:
            preprocessed = model_loader.preprocess_image(original_image)
            predictions  = model_loader.predict(preprocessed)
        except ImportError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=503)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

        # ✅ Use stored DB values so confidence always matches the Results tab.
        severity_result = _severity_result_from_db(diagnosis)

        has_caries, adaptive_affected = _adaptive_has_caries(severity_result, predictions)

        model = model_loader.load_model()
        if model is None:
            return JsonResponse({'success': False, 'error': 'Model could not be loaded'}, status=500)

        try:
            xai = XAIVisualizer(model)
            fig = xai.create_explanation_report(
                original_image=original_image,
                preprocessed_image=preprocessed,
                segmentation_mask=predictions,
                severity_result=severity_result,   # ← DB values, not re-inferred
            )
        except ImportError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=503)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

        output_filename = f'xai_explanation_{diagnosis_id}.png'
        output_path     = output_dir / output_filename
        xai.save_explanation(fig, output_path)

        supa_path = f"xai/{diagnosis_id}/xai_explanation_{diagnosis_id}.png"
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)

        fallback        = f"{settings.MEDIA_URL}dental_images/{output_filename}"
        explanation_url = _upload_to_supabase(supa_path, buf.getvalue(), fallback)

        if has_caries:
            interpretation = {
                'status':         'Caries Detected',
                'red_areas':      'Suspected caries regions requiring clinical review',
                'brightness':     'Confidence level (brighter = higher confidence)',
                'gradcam':        'Shows which regions influenced the AI decision most',
                'recommendation': 'Review red-highlighted areas during clinical examination',
            }
        else:
            interpretation = {
                'status':         'No Caries Detected',
                'red_areas':      'No significant caries regions detected',
                'brightness':     'All confidence values below detection threshold',
                'gradcam':        'Model found no significant areas of concern',
                'recommendation': 'Routine monitoring recommended, no immediate intervention needed',
            }

        return JsonResponse({
            'success':             True,
            'diagnosis_id':        diagnosis_id,
            'explanation_url':     explanation_url,
            # ✅ All numeric fields sourced from DB — always consistent with Results tab
            'severity':            severity_result['severity'],
            'confidence':          severity_result['confidence'],
            'affected_percentage': adaptive_affected,
            'mean_probability':    severity_result['mean_probability'],
            'max_probability':     severity_result['max_probability'],
            'has_caries':          bool(has_caries),
            'techniques_used': [
                'Segmentation Heatmap',
                'Grad-CAM',
                'Probability Overlay',
                'Binary Thresholding',
                'Statistical Analysis',
            ],
            'interpretation': interpretation,
        })

    except DiagnosisResult.DoesNotExist:
        return JsonResponse(
            {'success': False, 'error': f'Diagnosis with id {diagnosis_id} not found'},
            status=404)
    except Exception as e:
        return JsonResponse(
            {'success': False, 'error': str(e), 'traceback': traceback.format_exc()},
            status=500)


def quick_xai_overlay(request, diagnosis_id):
    try:
        diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)

        original_image, output_dir_or_error = _load_image_and_output_dir(diagnosis)
        if original_image is None:
            return JsonResponse({"success": False, "error": output_dir_or_error}, status=500)
        output_dir = output_dir_or_error

        preprocessed = model_loader.preprocess_image(original_image)
        predictions  = model_loader.predict(preprocessed)

        # ✅ Use stored DB values
        severity_result             = _severity_result_from_db(diagnosis)
        has_caries, adaptive_affected = _adaptive_has_caries(severity_result, predictions)

        xai        = XAIVisualizer(model_loader.load_model())
        overlay, _ = xai.visualize_segmentation_overlay(original_image, predictions)

        output_filename = f'xai_quick_{diagnosis_id}.png'
        output_path     = output_dir / output_filename
        cv2.imwrite(str(output_path), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))

        supa_path = f"xai/{diagnosis_id}/xai_quick_{diagnosis_id}.png"
        ok, png_arr = cv2.imencode('.png', cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
        if not ok:
            raise RuntimeError('Failed to encode quick overlay PNG')

        fallback    = f"{settings.MEDIA_URL}dental_images/{output_filename}"
        overlay_url = _upload_to_supabase(supa_path, png_arr.tobytes(), fallback)

        description = (
            f'Red areas indicate suspected caries ({adaptive_affected:.2f}% affected)'
            if has_caries
            else 'No caries detected - original peri-apical X-ray shows healthy tissue'
        )

        return JsonResponse({
            'success':             True,
            'diagnosis_id':        diagnosis_id,
            'overlay_url':         overlay_url,
            'has_caries':          bool(has_caries),
            'affected_percentage': adaptive_affected,
            'description':         description,
        })

    except DiagnosisResult.DoesNotExist:
        return JsonResponse(
            {'success': False, 'error': f'Diagnosis with id {diagnosis_id} not found'},
            status=404)
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
        predictions  = model_loader.predict(preprocessed)

        # ✅ Use stored DB values
        severity_result             = _severity_result_from_db(diagnosis)
        has_caries, adaptive_affected = _adaptive_has_caries(severity_result, predictions)

        xai             = XAIVisualizer(model_loader.load_model())
        gradcam         = xai.generate_gradcam(preprocessed)
        gradcam_overlay = xai.overlay_heatmap(gradcam, original_image)

        output_filename = f'gradcam_{diagnosis_id}.png'
        output_path     = output_dir / output_filename
        cv2.imwrite(str(output_path), cv2.cvtColor(gradcam_overlay, cv2.COLOR_RGB2BGR))

        supa_path = f"xai/{diagnosis_id}/gradcam_{diagnosis_id}.png"
        ok, png_arr = cv2.imencode('.png', cv2.cvtColor(gradcam_overlay, cv2.COLOR_RGB2BGR))
        if not ok:
            raise RuntimeError('Failed to encode Grad-CAM PNG')

        fallback    = f"{settings.MEDIA_URL}dental_images/{output_filename}"
        gradcam_url = _upload_to_supabase(supa_path, png_arr.tobytes(), fallback)

        description = (
            'Heatmap showing which regions influenced the caries detection (brighter = more influential)'
            if has_caries
            else 'Heatmap showing model analysis - no significant areas of concern identified'
        )

        return JsonResponse({
            'success':             True,
            'diagnosis_id':        diagnosis_id,
            'gradcam_url':         gradcam_url,
            # ✅ Consistent with Results tab
            'severity':            severity_result['severity'],
            'confidence':          severity_result['confidence'],
            'has_caries':          bool(has_caries),
            'affected_percentage': adaptive_affected,
            'description':         description,
        })

    except DiagnosisResult.DoesNotExist:
        return JsonResponse(
            {'success': False, 'error': f'Diagnosis with id {diagnosis_id} not found'},
            status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)    