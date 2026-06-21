"""Rutas del Portal de Jóvenes (rol GENERAL), montadas en /portal/ con namespace `youth`.

Todas son de consulta salvo `encuesta_responder` (FormView), el único endpoint de escritura
permitido (crea `TestSession` + `Answer`).
"""

from django.urls import path

from records import views as record_views

from . import youth_views as views

app_name = "youth"

urlpatterns = [
    path("", views.YouthDashboardView.as_view(), name="dashboard"),

    path("programas/", views.ProgramasListView.as_view(), name="programas"),
    path("programas/<int:pk>/", views.ProgramaDetailView.as_view(), name="programa_detalle"),

    path("eventos/", views.EventosListView.as_view(), name="eventos"),
    path("eventos/<int:pk>/", views.EventoDetailView.as_view(), name="evento_detalle"),

    path("descuentos/", views.DescuentosListView.as_view(), name="descuentos"),
    path("descuentos/<int:pk>/", views.DescuentoDetailView.as_view(), name="descuento_detalle"),

    path("encuestas/", views.EncuestasListView.as_view(), name="encuestas"),
    path("encuestas/<int:pk>/responder/", views.TestResponderView.as_view(), name="encuesta_responder"),

    path("mapa/", views.MapaView.as_view(), name="mapa"),
    path("api/mapa/", views.MapaDataView.as_view(), name="mapa_data"),

    # --- Expediente Digital (consulta propia + endpoints AJAX de bitácora) ---
    path("expediente/", record_views.MyRecordView.as_view(), name="expediente"),
    path("expediente/favorito/", record_views.ToggleFavoriteView.as_view(), name="toggle_favorito"),
    path("expediente/busqueda/", record_views.LogSearchView.as_view(), name="log_busqueda"),
]
