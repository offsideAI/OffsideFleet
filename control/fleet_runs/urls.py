from django.urls import path

from . import views

urlpatterns = [
    path("runs", views.runs),
    path("runs/<uuid:run_id>", views.run_detail),
    path("runs/<uuid:run_id>/steps", views.run_steps),
    path("runs/<uuid:run_id>/kill", views.run_kill),
]
