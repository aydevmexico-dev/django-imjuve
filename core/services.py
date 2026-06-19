"""
Consultas reutilizables para la landing pública.

Las usa tanto la vista `landing` (render inicial, q vacío) como el endpoint `buscar_api`
(filtrado en vivo), para no duplicar la lógica de búsqueda. Devuelven listas de dicts
serializables a JSON (fechas como ISO o None).
"""

from django.db.models import Q
from django.utils import timezone

from programs.models import Event, Program
from promotions.models import Promotion

from core.geodata import centroid_for

# Tope defensivo de resultados por consulta (los datos de dominio son pequeños, pero evita
# payloads enormes si algún día crecen).
RESULT_LIMIT = 200


def _fmt(date):
    return date.isoformat() if date else None


def _is_active(start, end, today):
    if start and start > today:
        return False
    if end and end < today:
        return False
    return True


def _serialize_geo(obj, kind):
    state_name = obj.state.name if obj.state else None
    lat, lng = centroid_for(state_name)
    return {
        "id": obj.id,
        "kind": kind,  # 'programa' | 'evento'
        "name": obj.name,
        "state": state_name,
        "municipality": obj.municipality.name if obj.municipality else None,
        "start_date": _fmt(obj.start_date),
        "end_date": _fmt(obj.end_date),
        "lat": lat,
        "lng": lng,
    }


def search_programas_eventos(q=""):
    """Programas + Eventos para los marcadores del mapa, posicionados por centroide estatal."""
    q = (q or "").strip()
    program_qs = Program.objects.select_related("state", "municipality")
    event_qs = Event.objects.select_related("state", "municipality", "city")

    if q:
        base = (
            Q(name__icontains=q)
            | Q(state__name__icontains=q)
            | Q(municipality__name__icontains=q)
        )
        # Program tiene M2M `cities`; Event tiene FK `city`.
        program_qs = program_qs.filter(base | Q(cities__name__icontains=q)).distinct()
        event_qs = event_qs.filter(base | Q(city__name__icontains=q)).distinct()

    results = [_serialize_geo(p, "programa") for p in program_qs[:RESULT_LIMIT]]
    results += [_serialize_geo(e, "evento") for e in event_qs[:RESULT_LIMIT]]
    return results


def search_descuentos(q=""):
    """Promociones (con su empresa) para el grid de tarjetas."""
    q = (q or "").strip()
    qs = Promotion.objects.select_related("company", "state", "municipality", "city")

    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(company__name__icontains=q)
            | Q(state__name__icontains=q)
            | Q(municipality__name__icontains=q)
            | Q(city__name__icontains=q)
        )

    today = timezone.localdate()
    results = []
    for promo in qs[:RESULT_LIMIT]:
        company = promo.company
        results.append(
            {
                "id": promo.id,
                "company": company.name if company else "",
                "logo_url": company.logo.url if (company and company.logo) else None,
                "name": promo.name,
                "description": promo.description or "",
                "state": promo.state.name if promo.state else None,
                "municipality": promo.municipality.name if promo.municipality else None,
                "city": promo.city.name if promo.city else None,
                "active": _is_active(promo.start_date, promo.end_date, today),
            }
        )
    return results
