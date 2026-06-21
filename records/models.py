"""Modelos del Expediente Digital del joven (rol GENERAL).

Bitácora automática + portafolio de identidad. Diseñado bajo el principio Abierto/Cerrado:
hoy guarda actividad (búsquedas, favoritos) y enlaza el historial de encuestas
(`tests.TestSession`); mañana albergará documentos digitalizados y estados de trámites sin
rehacer el esquema (ver `RecordDocument`).

Convención del repo: `verbose_name`s en español, identificadores en inglés. El favorito
`SavedItem` reusa el patrón de FKs nullable de `programs.Requirements`/`programs.Images`.
"""

from django.conf import settings
from django.db import models


class DigitalRecord(models.Model):
    """Contenedor raíz del expediente: un único registro por joven (rol GENERAL)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="digital_record",
        verbose_name="Usuario",
    )
    created_at = models.DateTimeField("Creado", auto_now_add=True)
    updated_at = models.DateTimeField("Actualizado", auto_now=True)

    class Meta:
        verbose_name = "Expediente Digital"
        verbose_name_plural = "Expedientes Digitales"

    def __str__(self):
        return f"Expediente de {self.user.email}"


class RecentSearch(models.Model):
    """Cada término que el joven escribe en el buscador superior, con su marca de tiempo."""

    record = models.ForeignKey(
        DigitalRecord,
        on_delete=models.CASCADE,
        related_name="searches",
        verbose_name="Expediente",
    )
    query = models.CharField("Búsqueda", max_length=200)
    created_at = models.DateTimeField("Fecha", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Búsqueda reciente"
        verbose_name_plural = "Búsquedas recientes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.query} ({self.created_at:%Y-%m-%d %H:%M})"


class SavedItem(models.Model):
    """Elemento guardado como favorito/interés. Apunta a EXACTAMENTE uno de los tres pilares.

    Espeja la convención de FKs nullable del repo (`Requirements`/`Images`). Un `CheckConstraint`
    garantiza que solo un FK esté presente; sendos `UniqueConstraint` impiden duplicados.
    """

    record = models.ForeignKey(
        DigitalRecord,
        on_delete=models.CASCADE,
        related_name="saved_items",
        verbose_name="Expediente",
    )
    program = models.ForeignKey(
        "programs.Program", on_delete=models.CASCADE, null=True, blank=True,
        related_name="saved_by", verbose_name="Programa",
    )
    event = models.ForeignKey(
        "programs.Event", on_delete=models.CASCADE, null=True, blank=True,
        related_name="saved_by", verbose_name="Evento",
    )
    promotion = models.ForeignKey(
        "promotions.Promotion", on_delete=models.CASCADE, null=True, blank=True,
        related_name="saved_by", verbose_name="Promoción",
    )
    created_at = models.DateTimeField("Guardado", auto_now_add=True)

    class Meta:
        verbose_name = "Elemento guardado"
        verbose_name_plural = "Elementos guardados"
        ordering = ["-created_at"]
        constraints = [
            # Exactamente uno de los tres FKs debe estar definido (XOR de tres vías).
            models.CheckConstraint(
                name="saveditem_exactly_one_target",
                check=(
                    models.Q(program__isnull=False, event__isnull=True, promotion__isnull=True)
                    | models.Q(program__isnull=True, event__isnull=False, promotion__isnull=True)
                    | models.Q(program__isnull=True, event__isnull=True, promotion__isnull=False)
                ),
            ),
            # Sin duplicados del mismo elemento dentro de un expediente.
            models.UniqueConstraint(
                fields=["record", "program"], name="uniq_saved_program",
                condition=models.Q(program__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["record", "event"], name="uniq_saved_event",
                condition=models.Q(event__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["record", "promotion"], name="uniq_saved_promotion",
                condition=models.Q(promotion__isnull=False),
            ),
        ]

    @property
    def kind(self):
        if self.program_id:
            return "programa"
        if self.event_id:
            return "evento"
        if self.promotion_id:
            return "descuento"
        return ""

    @property
    def target(self):
        """Devuelve el objeto guardado (Program/Event/Promotion) o None."""
        return self.program or self.event or self.promotion

    def __str__(self):
        t = self.target
        return f"{self.kind}: {t}" if t else "Elemento guardado (huérfano)"


class RecordDocument(models.Model):
    """Documento digitalizado del expediente. Reservado para fases de trámites formales.

    Definido desde ahora (Abierto/Cerrado) para no rehacer la base al habilitar inscripciones:
    todos los campos operativos quedan opcionales (`blank/null`) y sin UI de carga por el momento.
    """

    class Status(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    record = models.ForeignKey(
        DigitalRecord,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="Expediente",
    )
    file = models.FileField(
        "Archivo", upload_to="records/docs/", null=True, blank=True,
    )
    document_type = models.CharField(
        "Tipo de documento", max_length=80, blank=True,
        help_text="Ej. Identificación, Comprobante de estudios.",
    )
    status = models.CharField(
        "Estatus", max_length=10, choices=Status.choices, default=Status.PENDIENTE,
    )
    uploaded_at = models.DateTimeField("Subido", auto_now_add=True)

    class Meta:
        verbose_name = "Documento del expediente"
        verbose_name_plural = "Documentos del expediente"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.document_type or 'Documento'} — {self.get_status_display()}"
