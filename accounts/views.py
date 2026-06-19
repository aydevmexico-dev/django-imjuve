"""Vistas de registro y login para Jóvenes."""

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import resolve_url
from django.urls import reverse_lazy
from django.views.generic import FormView

from .forms import EmailAuthenticationForm, YouthRegistrationForm

CustomUser = get_user_model()


class RegistroView(SuccessMessageMixin, FormView):
    """Alta de un Joven. Crea CustomUser+YouthProfile (atómico en el form) y auto-inicia sesión."""

    template_name = "accounts/registro.html"
    form_class = YouthRegistrationForm
    success_url = reverse_lazy("landing")
    success_message = "¡Cuenta creada! Bienvenido(a) a la plataforma."

    def form_valid(self, form):
        user = form.save()          # creación atómica de usuario + perfil
        login(self.request, user)   # sesión activa inmediatamente tras registrarse
        return super().form_valid(form)


class RoleBasedLoginView(auth_views.LoginView):
    """Login por email con redirección según rol.

    Respeta `next` cuando viene en la petición (p. ej. al ser rebotado desde una página
    protegida). Si no hay `next`, los administradores (SUPER/ESTATAL) van al Panel y los
    Jóvenes (GENERAL) a la landing pública. Esto corrige el bug por el que todos caían en la
    landing tras iniciar sesión.
    """

    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        # Solo se usa cuando NO hay un `next` seguro; `get_success_url()` prioriza `next`.
        user = self.request.user
        if getattr(user, "role", None) in {CustomUser.Role.SUPER, CustomUser.Role.ESTATAL}:
            return resolve_url("panel:dashboard")
        return resolve_url(settings.LOGIN_REDIRECT_URL)
