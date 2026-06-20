"""Formularios de alta/edición de Empresas y Promociones (descuentos) con scope territorial."""

from django import forms

from core.forms import GeoScopedModelForm

from .models import Company, Promotion


class CompanyForm(GeoScopedModelForm):
    """Empresa de la red de beneficios. Su única geografía es el Estado: queda bloqueado
    al estado del Administrador Estatal y libre (incl. Nacional) para el Super."""

    geo_municipality_field = None
    geo_city_field = None

    class Meta:
        model = Company
        fields = ["name", "state", "logo", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class PromotionForm(GeoScopedModelForm):
    """Promoción de una Empresa. Geografía propia: Estado + Municipio + Ciudad (FK).

    El desplegable de `company` se pre-filtra por rol: el Administrador Estatal solo ve
    empresas de su estado asignado; el Super ve todas.
    """

    class Meta:
        model = Promotion
        fields = [
            "company", "name", "state", "municipality", "city",
            "start_date", "end_date", "requirements", "access_link",
            "image", "description",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "requirements": forms.Textarea(attrs={"rows": 3}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aislamiento territorial del desplegable de Empresa (el Super ve todas).
        if self._scope_state_id:
            self.fields["company"].queryset = Company.objects.filter(state_id=self._scope_state_id)
