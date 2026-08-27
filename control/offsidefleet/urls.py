from django.urls import include, path

urlpatterns = [
    path("", include("fleet_core.urls")),
    path("api/v1/", include("fleet_runs.urls")),
    path("internal/", include("fleet_runs.internal_urls")),
]
