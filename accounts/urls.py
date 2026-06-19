"""Rutas de registro y autenticación de Jóvenes."""

from django.contrib.auth import views as auth_views
from django.urls import path

from .views import RegistroView, RoleBasedLoginView

app_name = "accounts"

urlpatterns = [
    path("registro/", RegistroView.as_view(), name="registro"),
    path("login/", RoleBasedLoginView.as_view(), name="login"),
    # LogoutView solo acepta POST en Django 5 (usar un <form> con csrf en la plantilla).
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
