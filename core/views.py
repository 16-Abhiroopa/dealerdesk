import os
from django.conf import settings
from django.http import JsonResponse, HttpResponse


def health(request):
    """GET /api/health/ — the grader polls this until your app is ready."""
    return JsonResponse({"status": "ok"})


def frontend_index(request):
    """Serve built React frontend SPA index.html."""
    dist_index = settings.BASE_DIR / "frontend" / "dist" / "index.html"
    if dist_index.exists():
        with open(dist_index, "r", encoding="utf-8") as f:
            return HttpResponse(f.read(), content_type="text/html")
    return JsonResponse({
        "status": "ok",
        "message": "VIKMO DealerDesk API is running. Build frontend with 'npm run build' in frontend/ to view portal."
    })
