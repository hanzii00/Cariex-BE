from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from dashboard.models import Patient
from ..models import DiagnosisResult
from ..supabase import supabase
from ..model_loader import model_loader
import uuid
import numpy as np
try:
    import cv2
except Exception as _:
    cv2 = None


@csrf_exempt
def upload_image(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST only'}, status=405)

    image = request.FILES.get('image')
    patient_id = request.POST.get('patient_id')

    if not image or not patient_id:
        return JsonResponse({
            'success': False,
            'message': 'Image and patient_id are required'
        }, status=400)

    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invalid patient'}, status=404)

    # Unique file path
    file_ext = image.name.split('.')[-1]
    file_name = f"{patient.id}/{uuid.uuid4()}.{file_ext}"

    # Upload to Supabase
    content = image.read()
    supabase.storage.from_("images").upload(
        file_name,
        content,
        {"content-type": image.content_type}
    )

    # Get public URL
    image_url = supabase.storage.from_("images").get_public_url(file_name)

    # Create diagnosis linked to patient
    diagnosis = DiagnosisResult.objects.create(
        user=request.user if request.user.is_authenticated else None,
        patient=patient,
        image_url=image_url,
        status='processing'
    )

    # Run model inference synchronously on the uploaded image bytes
    try:
        if cv2 is None:
            # OpenCV not available; skip synchronous inference in this environment
            print('Skipping model inference: cv2 not installed')
        else:
            nparr = np.frombuffer(content, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                pre = model_loader.preprocess_image(img)
                preds = model_loader.predict(pre)
                result = model_loader.classify_severity(preds)

                # Determine has_caries and confidence
                severity = result.get('severity')
                confidence = result.get('confidence') or result.get('confidence_score') or 0.0

                if 'affected_percentage' in result:
                    has_caries = result['affected_percentage'] >= 1
                else:
                    has_caries = severity is not None and severity != 'Normal'

                # Generate bounding boxes
                lesion_boxes = None
                if 'segmentation_mask' in result and result['segmentation_mask'] is not None:
                    lesion_boxes = model_loader.generate_bounding_boxes(result['segmentation_mask'])

                diagnosis.has_caries = bool(has_caries)
                diagnosis.severity = severity or ''
                diagnosis.confidence_score = float(confidence) if confidence is not None else None
                diagnosis.lesion_boxes = lesion_boxes
                diagnosis.status = 'completed'
                diagnosis.save()
            else:
                # Could not decode image — leave as processing
                pass
    except Exception as e:
        # Log but don't fail the upload — keep status as processing so background worker can retry
        print('Model inference error:', e)

    return JsonResponse({
        'success': True,
        'diagnosis_id': diagnosis.id,
        'image_url': image_url,
        'status': diagnosis.status,
        'has_caries': diagnosis.has_caries,
        'severity': diagnosis.severity,
        'confidence_score': diagnosis.confidence_score,
        'lesion_boxes': diagnosis.lesion_boxes,
    })
