"""
Consultas reutilizables para la landing pública.

Las usa tanto la vista `landing` (render inicial, q vacío) como el endpoint `buscar_api`
(filtrado en vivo), para no duplicar la lógica de búsqueda. Devuelven listas de dicts
serializables a JSON (fechas como ISO o None).

También aloja el servicio de **geolocalización por IP** del portal de jóvenes
(`detect_youth_state`), que estima el Estado desde donde se conecta el joven para priorizar
contenido cercano, con respaldo a su Estado de residencia registrado.
"""

import ipaddress
import json
import logging
import urllib.request

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.utils import timezone

from programs.models import Event, Program
from promotions.models import Promotion
from states.models import State

from core.geodata import _strip_accents, centroid_for

logger = logging.getLogger(__name__)

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


# ============================================================================
# Geolocalización por IP (portal de jóvenes)
# ============================================================================
# Estima el Estado desde donde se conecta el joven para priorizar contenido cercano.
# Es BEST-EFFORT: ante cualquier fallo (IP privada/local, timeout, país != MX, nombre que
# no mapea) devuelve None y la vista cae al Estado de residencia del perfil. Usa la stdlib
# (`urllib`) para no añadir dependencias; el resultado se cachea en `request.session`.

IP_API_URL = "http://ip-api.com/json/{ip}?fields=status,countryCode,regionName"
IP_API_TIMEOUT = 2.0  # segundos; corto para no bloquear la carga de la página
SESSION_GEO_KEY = "youth_geo"   # {"state_id": int|None, "source": str}

# ip-api regresa `regionName` en formas que no coinciden con el catálogo SEPOMEX (MAYÚSCULAS,
# forma larga). Alias para los casos que el cotejo por subcadena no resuelve solo.
_REGION_ALIASES = {
    "MEXICO CITY": "DISTRITO FEDERAL",
    "CIUDAD DE MEXICO": "DISTRITO FEDERAL",
    "CDMX": "DISTRITO FEDERAL",
    "STATE OF MEXICO": "MEXICO",
    "ESTADO DE MEXICO": "MEXICO",
}


def client_ip(request):
    """IP pública del cliente: primera de `X-Forwarded-For`, si no `REMOTE_ADDR`."""
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "").strip()


def _match_state(region_name):
    """Mapea el `regionName` de ip-api a un `State` del catálogo (cotejo tolerante)."""
    if not region_name:
        return None
    norm = _strip_accents(region_name).upper().strip()
    norm = _REGION_ALIASES.get(norm, norm)
    index = {_strip_accents(s.name).upper(): s for s in State.objects.all()}
    if norm in index:
        return index[norm]
    # Respaldo por subcadena: "VERACRUZ" ⊂ "VERACRUZ DE IGNACIO DE LA LLAVE", etc.
    for key, state in index.items():
        if norm and (norm in key or key in norm):
            return state
    return None


def state_from_ip(ip):
    """Consulta ip-api y devuelve el `State` mexicano detectado, o None. Nunca lanza."""
    if not ip:
        return None
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_reserved:
            return None   # localhost / red interna: ip-api no resolvería
    except ValueError:
        return None
    try:
        with urllib.request.urlopen(IP_API_URL.format(ip=ip), timeout=IP_API_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:   # noqa: BLE001 — timeout, red, JSON inválido: degradamos a None
        logger.warning("Geolocalización por IP no disponible para %s", ip, exc_info=True)
        return None
    if data.get("status") != "success" or data.get("countryCode") != "MX":
        return None
    return _match_state(data.get("regionName"))


def _profile_state_id(user):
    """Estado de residencia registrado: youth_profile → residence_location → municipio → estado."""
    try:
        profile = user.youth_profile
    except ObjectDoesNotExist:
        return None
    loc = profile.residence_location if profile else None
    if loc and loc.municipality_id:
        return loc.municipality.state_id
    return None


def detect_youth_state(request, user):
    """Estado efectivo del joven para priorizar contenido. Devuelve `(state_id, source)`.

    Orden: caché de sesión → IP (solo si ip-api resuelve un Estado MX) → Estado del perfil.
    `source` ∈ {"ip", "perfil", "desconocido"} para etiquetar la UI. Cachea en sesión para no
    pegarle a ip-api en cada request.
    """
    cached = request.session.get(SESSION_GEO_KEY)
    if isinstance(cached, dict) and "state_id" in cached:
        return cached["state_id"], cached.get("source", "perfil")

    state = state_from_ip(client_ip(request))
    if state is not None:
        state_id, source = state.id, "ip"
    else:
        state_id = _profile_state_id(user)
        source = "perfil" if state_id else "desconocido"

    request.session[SESSION_GEO_KEY] = {"state_id": state_id, "source": source}
    return state_id, source
