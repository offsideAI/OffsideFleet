from django.urls import path

from . import internal_views

urlpatterns = [
    path("callbacks/runs/<uuid:run_id>/steps", internal_views.append_steps),
    path("callbacks/runs/<uuid:run_id>/state", internal_views.set_state),
]
