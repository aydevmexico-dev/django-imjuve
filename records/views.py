"""Vistas del Expediente Digital (rol GENERAL).

`MyRecordView` muestra SIEMPRE el expediente de `request.user` (no acepta `pk` → IDOR
imposible). `ToggleFavoriteView` y `LogSearchView` son endpoints AJAX (POST con CSRF) que
alimentan el expediente en segundo plano. La regla por defecto es **denegar**: cualquier rol
distinto de GENERAL (o un administrador en modo vista previa) recibe 403 en las escrituras.

El historial de encuestas se lee directamente de `tests.TestSession` (sin modelo espejo).
"""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from programs.models import Event, Program
from promotions.models import Promotion
from tests.models import TestSession

from core.youth_views import YouthAccessMixin, _date_label, _location_label

from .models import DigitalRecord, RecentSearch, SavedItem

CustomUser = get_user_model()

# kind público (URL/JS) -> (Modelo, nombre del campo FK en SavedItem, nombre de ruta de detalle)
SAVED_KINDS = {
    "programa": (Program, "program", "youth:programa_detalle"),
    "evento": (Event, "event", "youth:evento_detalle"),
    "descuento": (Promotion, "promotion", "youth:descuento_detalle"),
}

MAX_QUERY_LEN = 200
RECENT_SEARCH_LIMIT = 20


def _is_general(user):
    """Fail-safe: solo el joven (GENERAL) escribe en su expediente."""
    return user.is_authenticated and user.role == CustomUser.Role.GENERAL


def build_saved_card(item):
    """Dict de presentación de un `SavedItem` (compartido por el portal joven y el panel admin).

    Incluye `obj_id` (pk del recurso, para des-guardar) y `detail_url` que se abre en pestaña
    nueva. Devuelve None si el recurso enlazado ya no existe.
    """
    obj = item.target
    if obj is None:
        return None
    kind = item.kind
    city = getattr(obj, "city", None)  # Program no tiene city; getattr lo cubre
    return {
        "saved_id": item.id,
        "obj_id": obj.pk,
        "kind": kind,
        "title": obj.name,
        "detail_url": reverse(SAVED_KINDS[kind][2], args=[obj.pk]),
        "image_url": obj.image.url if getattr(obj, "image", None) else None,
        "location": _location_label(obj.state, getattr(obj, "municipality", None), city),
        "date_label": _date_label(
            getattr(obj, "start_date", None), getattr(obj, "end_date", None)
        ),
    }


# ---------------------------------------------------------------------------
# Expediente propio (solo lectura para el joven)
# ---------------------------------------------------------------------------
class MyRecordView(YouthAccessMixin, TemplateView):
    template_name = "youth/my_record.html"
    active_nav = "expediente"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # El expediente solo existe para jóvenes. El admin en vista previa ve el cascarón vacío.
        record = None
        if _is_general(user):
            record, _ = DigitalRecord.objects.get_or_create(user=user)

        saved_cards, historial, searches = [], [], []
        if record:
            saved_qs = record.saved_items.select_related(
                "program__state", "program__municipality",
                "event__state", "event__municipality", "event__city",
                "promotion__state", "promotion__municipality", "promotion__city",
            )
            saved_cards = [c for c in (build_saved_card(i) for i in saved_qs) if c]
            historial = (
                TestSession.objects.filter(user=user)
                .select_related("test")
                .order_by("-completed_at")
            )
            searches = record.searches.all()[:RECENT_SEARCH_LIMIT]

        ctx.update({
            "record": record,
            "youth_profile": self.youth_profile,
            "saved_cards": saved_cards,
            "saved_programas_eventos": [c for c in saved_cards if c["kind"] != "descuento"],
            "saved_descuentos": [c for c in saved_cards if c["kind"] == "descuento"],
            "historial": historial,
            "searches": searches,
        })
        return ctx


# ---------------------------------------------------------------------------
# Endpoints AJAX (escritura) — POST + CSRF, solo GENERAL
# ---------------------------------------------------------------------------
@method_decorator(require_POST, name="dispatch")
class ToggleFavoriteView(LoginRequiredMixin, View):
    """Alterna un favorito del expediente del propio usuario. Devuelve {'saved': bool}."""

    def post(self, request, *args, **kwargs):
        if not _is_general(request.user):
            return JsonResponse({"detail": "No autorizado."}, status=403)

        kind = (request.POST.get("kind") or "").strip()
        raw_id = request.POST.get("id") or ""
        if kind not in SAVED_KINDS or not raw_id.isdigit():
            return JsonResponse({"detail": "Solicitud inválida."}, status=400)

        model, fk_field, _ = SAVED_KINDS[kind]
        obj = get_object_or_404(model, pk=int(raw_id))

        record, _created = DigitalRecord.objects.get_or_create(user=request.user)
        existing = record.saved_items.filter(**{fk_field: obj}).first()
        if existing:
            existing.delete()
            return JsonResponse({"saved": False})

        SavedItem.objects.create(record=record, **{fk_field: obj})
        return JsonResponse({"saved": True})


@method_decorator(require_POST, name="dispatch")
class LogSearchView(LoginRequiredMixin, View):
    """Registra un término de búsqueda en el expediente. Fire-and-forget (204)."""

    def post(self, request, *args, **kwargs):
        if not _is_general(request.user):
            return JsonResponse({"detail": "No autorizado."}, status=403)

        # Acepta tanto form-encoded como JSON (el JS envía form-encoded).
        query = (request.POST.get("q") or "").strip()
        if not query and request.content_type == "application/json":
            try:
                query = (json.loads(request.body or "{}").get("q") or "").strip()
            except (ValueError, TypeError):
                query = ""
        if not query:
            return JsonResponse({"detail": "Vacío."}, status=400)

        record, _created = DigitalRecord.objects.get_or_create(user=request.user)
        RecentSearch.objects.create(record=record, query=query[:MAX_QUERY_LEN])
        return JsonResponse({}, status=204)
