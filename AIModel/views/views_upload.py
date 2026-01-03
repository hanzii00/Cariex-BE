from django.http import JsonResponse
from ..models import DiagnosisResult

def upload_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        image_file = request.FILES['image']
        
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

    return JsonResponse({
        'success': False,
        'message': 'Invalid request. Please upload an image using POST.'
    }, status=400)
