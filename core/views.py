"""Vistas públicas de la landing IMJUVE."""

from django.http import JsonResponse
from django.shortcuts import render

from states.models import State

from core.services import (
    destacados_convocatorias,
    search_descuentos,
    search_programas_eventos,
)


def landing(request):
    """Landing en `/`.

    Alimenta SIMULTÁNEAMENTE las tres zonas dinámicas de la página:
      · `programas`  → pines del mapa (y dataset inicial del buscador), embebido vía json_script.
      · `descuentos` → tarjetas de la vista alterna del buscador, embebido vía json_script.
      · `destacados` → feed lateral "Convocatorias de última hora", renderizado en servidor.
    """
    context = {
        "programas": search_programas_eventos(""),
        "descuentos": search_descuentos(""),
        "destacados": destacados_convocatorias(limit=6),
        "states": State.objects.order_by("name"),
    }
    return render(request, "landing.html", context)


def buscar_api(request):
    """Endpoint JSON de búsqueda en vivo: /api/buscar/?tipo=programas|descuentos&q=texto"""
    tipo = request.GET.get("tipo", "programas")
    q = request.GET.get("q", "")

    if tipo == "descuentos":
        results = search_descuentos(q)
    else:
        tipo = "programas"
        results = search_programas_eventos(q)

    return JsonResponse({"tipo": tipo, "q": q, "count": len(results), "results": results})
