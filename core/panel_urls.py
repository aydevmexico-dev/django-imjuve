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

    # --- Altas y ediciones (formularios con aislamiento territorial) ---
    path("programas/programa/crear/", views.ProgramCreateView.as_view(), name="programa_crear"),
    path("programas/programa/<int:pk>/editar/", views.ProgramUpdateView.as_view(), name="programa_editar"),
    path("programas/evento/crear/", views.EventCreateView.as_view(), name="evento_crear"),
    path("programas/evento/<int:pk>/editar/", views.EventUpdateView.as_view(), name="evento_editar"),
    path("descuentos/empresa/crear/", views.CompanyCreateView.as_view(), name="empresa_crear"),
    path("descuentos/empresa/<int:pk>/editar/", views.CompanyUpdateView.as_view(), name="empresa_editar"),
    path("descuentos/crear/", views.PromotionCreateView.as_view(), name="descuento_crear"),
    path("descuentos/<int:pk>/editar/", views.PromotionUpdateView.as_view(), name="descuento_editar"),
    path("encuestas/crear/", views.EncuestaCreateView.as_view(), name="encuesta_crear"),
    path("encuestas/<int:pk>/editar/", views.EncuestaUpdateView.as_view(), name="encuesta_editar"),
]
