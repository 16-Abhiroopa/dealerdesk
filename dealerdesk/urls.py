from django.contrib import admin
from django.urls import include, path, re_path
from core.views import frontend_index

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/", include("products.urls")),
    path("api/", include("dealers.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("assistant.urls")),
    path("api/", include("forecasting.urls")),
    re_path(r"^(?!api/|admin/).*$", frontend_index, name="frontend"),
]
