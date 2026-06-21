from django.apps import AppConfig


class RecordsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'records'
    verbose_name = 'Expedientes Digitales'

    def ready(self):
        # Conecta el signal que autocrea el expediente de cada joven (rol GENERAL).
        from . import signals  # noqa: F401
