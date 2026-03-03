from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@require_http_methods(["GET", "HEAD", "OPTIONS"])
def health_check(request):
    """Simple health check for uptime monitors (returns 200)."""
    return JsonResponse({"status": "ok"}, status=200)
