"""Rutas de los endpoints geográficos auxiliares."""

from django.urls import path

from . import views

app_name = "states"

urlpatterns = [
    path("api/geo/municipios/", views.municipios, name="municipios"),
    path("api/geo/colonias/", views.colonias, name="colonias"),
]
