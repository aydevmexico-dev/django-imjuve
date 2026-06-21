"""Automatización transparente del expediente.

Espeja el patrón de `accounts.YouthProfile`: cada `CustomUser` de rol GENERAL queda enlazado a
un único `DigitalRecord` sin intervención manual. Las búsquedas y favoritos se registran desde
las vistas AJAX (`records.views`), no aquí, para no acoplar el logging al ciclo de guardado.
"""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DigitalRecord


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_digital_record(sender, instance, **kwargs):
    """Crea el expediente del joven la primera vez (idempotente)."""
    # Importación diferida para evitar ciclos en el arranque de apps.
    from accounts.models import CustomUser

    if instance.role == CustomUser.Role.GENERAL:
        DigitalRecord.objects.get_or_create(user=instance)
