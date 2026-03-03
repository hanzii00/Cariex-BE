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
    """Ping Supabase with a tiny query to keep the project awake."""
    try:
        # Query a small, safe table. Replace 'keepalive' with an existing small table
        # or create one (single row) in Supabase for this purpose.
        resp = supabase.table("keepalive").select("id").limit(1).execute()
        # If the client returns an error key, consider it a failure
        if hasattr(resp, "error") and resp.error:
            return JsonResponse({"status": "error", "detail": str(resp.error)}, status=500)

        return JsonResponse({"status": "ok", "detail": "Supabase awake"}, status=200)
    except Exception as e:
        return JsonResponse({"status": "error", "detail": str(e)}, status=500)
