"""Formularios base del panel con aislamiento territorial por rol.

`GeoScopedModelForm` recorta los campos geográficos (Estado/Municipio/Ciudad/Ciudades)
según el usuario que la vista inyecta vía `get_form_kwargs`:

* **ESTATAL** → el Estado queda **bloqueado** a su `assigned_state` (Django ignora el POST
  de un campo `disabled` y usa el `initial`, así que es a prueba de manipulación) y
  Municipio/Ciudad/Ciudades solo ofrecen registros de ese estado.
* **SUPER** → ve todo el país; Municipio/Ciudad parten vacíos y se pueblan por cascada
  (POST o instancia en edición), igual que el registro de jóvenes (`accounts/forms.py`).

Misma filosofía que `StateScopedAdminMixin` del admin, pero para los ModelForm del panel.
No toca modelos ni admin.
"""

from django import forms

from accounts.models import CustomUser
from states.models import City, Municipality, State


def _widget_css_class(widget):
    """Clase CSS institucional según el tipo de widget (cero estilos inline en HTML)."""
    if isinstance(widget, (forms.Select, forms.SelectMultiple)):
        return "form-select"
    if isinstance(widget, forms.Textarea):
        return "form-textarea"
    if isinstance(widget, forms.CheckboxInput):
        return "form-check"
    return "form-input"


class GeoScopedModelForm(forms.ModelForm):
    """ModelForm que filtra la geografía por rol. La vista le pasa `user`."""

    # Nombres de los campos geográficos del modelo concreto (las subclases ajustan).
    geo_state_field = "state"
    geo_municipality_field = "municipality"
    geo_city_field = "city"      # FK singular (Event/Promotion/Test); None si no aplica
    geo_cities_field = None      # M2M (Program); None si no aplica

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self._scope_state_id = (
            user.assigned_state_id
            if user is not None and user.role == CustomUser.Role.ESTATAL
            else None
        )
        self._setup_geo_fields()
        self._stamp_widget_classes()

    # ------------------------------- Geografía -------------------------------
    def _resolve_state_id(self):
        """Estado vigente: ESTATAL siempre el suyo; SUPER toma POST > instancia > nada."""
        if self._scope_state_id:
            return self._scope_state_id
        bound_name = self.add_prefix(self.geo_state_field)
        if self.is_bound and self.data.get(bound_name):
            try:
                return int(self.data.get(bound_name))
            except (TypeError, ValueError):
                return None
        return getattr(self.instance, f"{self.geo_state_field}_id", None)

    def _setup_geo_fields(self):
        state_field = self.fields.get(self.geo_state_field)
        if state_field is not None:
            if self._scope_state_id:
                # ESTATAL: una sola opción, preseleccionada y bloqueada.
                state_field.queryset = State.objects.filter(id=self._scope_state_id)
                state_field.initial = self._scope_state_id
                state_field.disabled = True
                state_field.widget.attrs["data-locked"] = "1"
            state_field.widget.attrs["data-geo"] = "state"

        state_id = self._resolve_state_id()
        self._scope_choice_field(self.geo_municipality_field, Municipality, state_id, "municipality")
        self._scope_choice_field(self.geo_city_field, City, state_id, "city")
        self._scope_choice_field(self.geo_cities_field, City, state_id, "cities")

    def _scope_choice_field(self, field_name, model, state_id, geo_marker):
        if not field_name:
            return
        field = self.fields.get(field_name)
        if field is None:
            return
        # Con estado resuelto → solo sus registros; sin estado (SUPER al inicio) → vacío,
        # la cascada JS lo llena. Mantiene el render ligero y valida el id recibido.
        field.queryset = model.objects.filter(state_id=state_id) if state_id else model.objects.none()
        field.widget.attrs["data-geo"] = geo_marker

    def _stamp_widget_classes(self):
        for field in self.fields.values():
            css = _widget_css_class(field.widget)
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {css}".strip()

    # ------------------------ Coherencia territorial -------------------------
    def clean(self):
        cleaned = super().clean()
        state = cleaned.get(self.geo_state_field)
        state_id = state.id if state else self._scope_state_id

        def _belongs(obj):
            return obj is None or state_id is None or obj.state_id == state_id

        muni = cleaned.get(self.geo_municipality_field)
        if not _belongs(muni):
            self.add_error(self.geo_municipality_field,
                           "El municipio no pertenece al estado seleccionado.")

        if self.geo_city_field:
            if not _belongs(cleaned.get(self.geo_city_field)):
                self.add_error(self.geo_city_field,
                               "La ciudad no pertenece al estado seleccionado.")

        if self.geo_cities_field:
            for city in cleaned.get(self.geo_cities_field) or []:
                if not _belongs(city):
                    self.add_error(self.geo_cities_field,
                                   "Hay ciudades que no pertenecen al estado seleccionado.")
                    break
        return cleaned
