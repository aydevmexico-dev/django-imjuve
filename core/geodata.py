"""
Centroides aproximados por entidad federativa.

La base de datos no almacena coordenadas (no hay PostGIS ni campos lat/lng), así que los
marcadores de Programas/Eventos se ubican en el centroide del Estado correspondiente. La
precisión a nivel municipal requeriría agregar coordenadas a los modelos más adelante.

Las claves coinciden con los nombres tal cual los guarda `State.save()` (en MAYÚSCULAS y con
la forma oficial larga del catálogo SEPOMEX). `centroid_for()` además normaliza acentos como
respaldo, y `DISTRITO FEDERAL` / `MÉXICO` se mapean a CDMX / Estado de México.
"""

import unicodedata

# Centro geográfico de México (respaldo cuando no hay coincidencia).
MEXICO_CENTER = (23.6, -102.5)

STATE_CENTROIDS = {
    "AGUASCALIENTES": (21.88, -102.29),
    "BAJA CALIFORNIA": (30.84, -115.28),
    "BAJA CALIFORNIA SUR": (25.30, -111.90),
    "CAMPECHE": (18.90, -90.50),
    "CHIAPAS": (16.75, -92.63),
    "CHIHUAHUA": (28.60, -106.10),
    "COAHUILA DE ZARAGOZA": (27.06, -101.71),
    "COLIMA": (19.12, -104.00),
    "DISTRITO FEDERAL": (19.43, -99.13),
    "DURANGO": (24.60, -104.70),
    "GUANAJUATO": (21.00, -101.30),
    "GUERRERO": (17.55, -99.50),
    "HIDALGO": (20.50, -98.80),
    "JALISCO": (20.60, -103.40),
    "MICHOACÁN DE OCAMPO": (19.50, -101.70),
    "MORELOS": (18.68, -99.10),
    "MÉXICO": (19.30, -99.70),
    "NAYARIT": (21.75, -104.85),
    "NUEVO LEÓN": (25.60, -100.00),
    "OAXACA": (17.00, -96.70),
    "PUEBLA": (19.00, -98.20),
    "QUERÉTARO": (20.59, -100.39),
    "QUINTANA ROO": (19.60, -88.30),
    "SAN LUIS POTOSÍ": (22.15, -100.98),
    "SINALOA": (24.80, -107.40),
    "SONORA": (29.30, -110.60),
    "TABASCO": (17.90, -92.90),
    "TAMAULIPAS": (24.30, -98.60),
    "TLAXCALA": (19.40, -98.20),
    "VERACRUZ DE IGNACIO DE LA LLAVE": (19.40, -96.40),
    "YUCATÁN": (20.90, -89.40),
    "ZACATECAS": (22.80, -102.60),
}


def _strip_accents(text):
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


# Índice normalizado (sin acentos, MAYÚSCULAS) para tolerar variantes menores en el nombre.
_NORMALIZED_INDEX = {
    _strip_accents(name).upper(): coords for name, coords in STATE_CENTROIDS.items()
}


def centroid_for(state_name):
    """Devuelve (lat, lng) para el nombre del estado; cae al centro de México si no hay match."""
    if not state_name:
        return MEXICO_CENTER
    name = state_name.strip().upper()
    if name in STATE_CENTROIDS:
        return STATE_CENTROIDS[name]
    return _NORMALIZED_INDEX.get(_strip_accents(name), MEXICO_CENTER)
