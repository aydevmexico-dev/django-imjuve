"""Rutas del Panel de Administración personalizado (prefijo /panel/)."""

from django.urls import path

from . import panel_views as views

app_name = "panel"

urlpatterns = [
    path("", views.DashboardIndexView.as_view(), name="dashboard"),
    path("programas/", views.ProgramasEventosView.as_view(), name="programas"),
    path("descuentos/", views.DescuentosView.as_view(), name="descuentos"),
    path("encuestas/", views.EncuestasView.as_view(), name="encuestas"),
    path("encuestas/sesiones/<int:pk>/", views.SesionDetalleView.as_view(), name="sesion_detalle"),
]
