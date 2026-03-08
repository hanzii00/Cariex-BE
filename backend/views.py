from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from utils import supabase


@csrf_exempt
@require_http_methods(["GET", "HEAD", "OPTIONS"])
def health_check(request):
    """Simple health check for uptime monitors (returns 200)."""
    return JsonResponse({"status": "ok"}, status=200)


@csrf_exempt
@require_http_methods(["GET", "HEAD", "OPTIONS"])
def keepalive(request):
    try:
        from utils import supabase  # import here, not at module level
        resp = supabase.table("keepalive").select("id").limit(1).execute()
        if hasattr(resp, "error") and resp.error:
            return JsonResponse({"status": "error", "detail": str(resp.error)}, status=500)
        return JsonResponse({"status": "ok", "detail": "Supabase awake"}, status=200)
    except Exception as e:
        return JsonResponse({"status": "error", "detail": str(e)}, status=500)
