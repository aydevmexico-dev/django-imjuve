"""Vistas públicas de la landing IMJUVE."""

from django.http import JsonResponse
from django.shortcuts import render

from states.models import State

from core.services import search_descuentos, search_programas_eventos


def landing(request):
    """Landing en `/` con los dos datasets iniciales (sin filtro) embebidos para el front."""
    context = {
        "programas": search_programas_eventos(""),
        "descuentos": search_descuentos(""),
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
