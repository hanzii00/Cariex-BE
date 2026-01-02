from django.shortcuts import render
from django.http import JsonResponse
from ..models import DiagnosisResult


def upload_image(request):
    """
    F4: Dental Image Upload & Acquisition
    Accepts image upload and creates diagnosis record
    """
    if request.method == 'POST' and request.FILES.get('image'):
        image_file = request.FILES['image']
        
        # Create diagnosis record
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