from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from dashboard.models import Patient
from ..models import DiagnosisResult
from ..supabase import supabase
import uuid


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
    supabase.storage.from_("images").upload(
        file_name,
        image.read(),
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

    return JsonResponse({
        'success': True,
        'diagnosis_id': diagnosis.id,
        'image_url': image_url,
        'status': diagnosis.status
    })
