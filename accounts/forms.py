"""Formularios de registro y login para Jóvenes (rol GENERAL)."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from states.models import Location, Municipality, State

from .models import YouthProfile

CustomUser = get_user_model()


class YouthRegistrationForm(forms.Form):
    """Registro de un Joven: crea CustomUser (rol GENERAL) + YouthProfile de forma atómica."""

    first_name = forms.CharField(label="Nombre(s)", max_length=150)
    last_name = forms.CharField(label="Apellidos", max_length=150)
    phone = forms.CharField(label="Teléfono", max_length=20)
    email = forms.EmailField(label="Correo electrónico")
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput)
    birthdate = forms.DateField(
        label="Fecha de nacimiento",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    postal_code = forms.CharField(label="Código Postal", max_length=10)

    # Geografía. Estado se renderiza completo (32 opciones); Municipio/Colonia los llena el JS,
    # por eso sus querysets se acotan dinámicamente en __init__ según los datos enviados.
    state = forms.ModelChoiceField(label="Estado", queryset=State.objects.all())
    municipality = forms.ModelChoiceField(label="Municipio", queryset=Municipality.objects.none())
    residence_location = forms.ModelChoiceField(
        label="Colonia / Asentamiento", queryset=Location.objects.none()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Querysets dependientes: solo se amplían si el POST trae el padre correspondiente.
        # Mantiene el render pequeño y permite que ModelChoiceField valide el id enviado.
        if self.data:
            try:
                state_id = int(self.data.get("state"))
                self.fields["municipality"].queryset = Municipality.objects.filter(state_id=state_id)
            except (TypeError, ValueError):
                pass
            try:
                municipality_id = int(self.data.get("municipality"))
                self.fields["residence_location"].queryset = Location.objects.filter(
                    municipality_id=municipality_id
                )
            except (TypeError, ValueError):
                pass

    def clean_email(self):
        # Email único (el manager normaliza a minúsculas, por eso comparamos case-insensitive).
        email = self.cleaned_data["email"].strip().lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise ValidationError("Ya existe una cuenta registrada con este correo electrónico.")
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")

        # Coincidencia y políticas de seguridad de contraseña.
        if password1 and password2:
            if password1 != password2:
                self.add_error("password2", "Las contraseñas no coinciden.")
            else:
                try:
                    validate_password(password1)
                except ValidationError as exc:
                    self.add_error("password1", exc)

        # Coherencia territorial: Municipio pertenece al Estado; Colonia pertenece al Municipio
        # y su CP coincide con el capturado (valida la existencia real de la Location).
        state = cleaned.get("state")
        municipality = cleaned.get("municipality")
        location = cleaned.get("residence_location")
        postal_code = cleaned.get("postal_code")

        if state and municipality and municipality.state_id != state.id:
            self.add_error("municipality", "El municipio no pertenece al estado seleccionado.")
        if municipality and location and location.municipality_id != municipality.id:
            self.add_error("residence_location", "La colonia no pertenece al municipio seleccionado.")
        if location and postal_code and location.postal_code != postal_code.strip():
            self.add_error("postal_code", "El código postal no coincide con la colonia seleccionada.")

        return cleaned

    @transaction.atomic
    def save(self):
        """Crea el usuario y su perfil en una sola transacción (rollback si algo falla)."""
        cd = self.cleaned_data
        user = CustomUser.objects.create_user(  # create_user hace set_password y role=GENERAL
            email=cd["email"],
            password=cd["password1"],
            first_name=cd["first_name"],
            last_name=cd["last_name"],
        )
        YouthProfile.objects.create(
            user=user,
            phone=cd["phone"],
            birthdate=cd["birthdate"],
            residence_postal_code=cd["postal_code"],
            residence_location=cd["residence_location"],
        )
        return user


class EmailAuthenticationForm(AuthenticationForm):
    """Login estricto por email. Mantiene el nombre interno `username` que espera authenticate()."""

    username = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"autofocus": True}),
    )
