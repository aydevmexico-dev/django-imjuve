"""Formularios de alta/edición de Programas y Eventos (panel, con scope territorial)."""

from django import forms

from core.forms import GeoScopedModelForm

from .models import Event, Program


class ProgramForm(GeoScopedModelForm):
    """Programa social. La geografía es Estado + Municipio (FK) + Ciudades (M2M)."""

    geo_city_field = None          # Program no tiene FK `city`...
    geo_cities_field = "cities"    # ...sino un M2M `cities`.

    class Meta:
        model = Program
        fields = [
            "name", "state", "municipality", "cities",
            "start_date", "end_date", "age_from", "age_to",
            "organizing_institution", "access_link", "image", "description",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class EventForm(GeoScopedModelForm):
    """Evento. Geografía: Estado + Municipio + Ciudad (FK singular)."""

    class Meta:
        model = Event
        fields = [
            "name", "state", "municipality", "city",
            "start_date", "end_date", "headquarters",
            "organizing_institution", "image", "description",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 4}),
        }
