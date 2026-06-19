"""Endpoints JSON auxiliares para la cascada geográfica del registro (públicos, read-only)."""

from django.http import JsonResponse

from .models import Location, Municipality

# Tope defensivo: una colonia/municipio puede tener muchos asentamientos.
RESULT_LIMIT = 500


def municipios(request):
    """GET /api/geo/municipios/?state=<id> -> [{id, name}] (drill-down Estado -> Municipio)."""
    state_id = request.GET.get("state")
    qs = Municipality.objects.none()
    if state_id:
        qs = Municipality.objects.filter(state_id=state_id).order_by("name")
    data = [{"id": m.id, "name": m.name} for m in qs[:RESULT_LIMIT]]
    return JsonResponse({"results": data})


def colonias(request):
    """GET /api/geo/colonias/?municipality=<id>  ó  ?postal_code=<cp>.

    - Por municipio: [{id, name, settlement_type, postal_code}].
    - Por CP: además incluye municipio y estado (una colonia ya implica ambos), para que el
      front autocomplete Estado/Municipio. `postal_code` está indexado => búsqueda eficiente.
    """
    postal_code = request.GET.get("postal_code")
    municipality_id = request.GET.get("municipality")

    if postal_code:
        qs = (
            Location.objects.filter(postal_code=postal_code.strip())
            .select_related("municipality", "municipality__state")
            .order_by("name")
        )
        data = [
            {
                "id": loc.id,
                "name": loc.name,
                "settlement_type": loc.settlement_type,
                "postal_code": loc.postal_code,
                "municipality_id": loc.municipality_id,
                "municipality": loc.municipality.name,
                "state_id": loc.municipality.state_id,
                "state": loc.municipality.state.name,
            }
            for loc in qs[:RESULT_LIMIT]
        ]
        return JsonResponse({"results": data})

    qs = Location.objects.none()
    if municipality_id:
        qs = Location.objects.filter(municipality_id=municipality_id).order_by("name")
    data = [
        {
            "id": loc.id,
            "name": loc.name,
            "settlement_type": loc.settlement_type,
            "postal_code": loc.postal_code,
        }
        for loc in qs[:RESULT_LIMIT]
    ]
    return JsonResponse({"results": data})
