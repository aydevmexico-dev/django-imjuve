from django.contrib import admin
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from .models import State, Municipality, City, Location

# --- Recursos para Import/Export ---

class LocationResource(resources.ModelResource):
    # 1. Mapeamos las columnas directas del Excel a los campos del modelo
    postal_code = fields.Field(column_name='Código', attribute='postal_code')
    name = fields.Field(column_name='Asentamiento', attribute='name')
    settlement_type = fields.Field(column_name='Tipo', attribute='settlement_type')
    
    # 2. Creamos campos virtuales para inyectar los IDs de las llaves foráneas
    municipality = fields.Field(attribute='municipality_id', column_name='municipality_id')
    city = fields.Field(attribute='city_id', column_name='city_id')

    class Meta:
        model = Location
        fields = ('postal_code', 'name', 'settlement_type', 'municipality', 'city')
        # Usamos estos campos para identificar si un registro ya existe y actualizarlo en vez de duplicarlo
        import_id_fields = ('postal_code', 'name', 'settlement_type')


    def before_import_row(self, row, **kwargs):
        """
        Esta función se ejecuta por cada fila ANTES de guardarla. 
        Aquí leemos el texto del Excel, buscamos/creamos los modelos padres, 
        y le pasamos los IDs resultantes al importador.
        """
        # 1. Resolver el Estado (Añadimos .upper() para evitar el fallo de UNIQUE constraint)
        estado_nombre_crudo = row.get('Estado')
        if estado_nombre_crudo:
            estado_nombre = str(estado_nombre_crudo).strip().upper()
        else:
            estado_nombre = "" # Por si viene vacío

        estado_obj, created = State.objects.get_or_create(
            name=estado_nombre
        )

        # 2. Resolver el Municipio (depende del estado)
        municipio_nombre_crudo = row.get('Municipio')
        if municipio_nombre_crudo:
            # Los normalizamos con title() o upper() según prefieras, aquí lo dejamos limpio
            municipio_nombre = str(municipio_nombre_crudo).strip() 
        else:
            municipio_nombre = ""

        municipio_obj, created = Municipality.objects.get_or_create(
            state=estado_obj,
            name=municipio_nombre
        )
        # Inyectamos el ID en la fila para que el Field 'municipality' lo tome
        row['municipality_id'] = municipio_obj.id

        # 3. Resolver la Ciudad (suele venir vacía en zonas rurales)
        ciudad_nombre = row.get('Ciudad')
        if ciudad_nombre and str(ciudad_nombre).strip():
            ciudad_obj, created = City.objects.get_or_create(
                state=estado_obj,
                name=str(ciudad_nombre).strip()
            )
            row['city_id'] = ciudad_obj.id
        else:
            row['city_id'] = None


# --- Clases Admin ---

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name', 'abbreviation')
    search_fields = ('name',)

@admin.register(Municipality)
class MunicipalityAdmin(admin.ModelAdmin):
    list_display = ('name', 'state')
    list_filter = ('state',)
    search_fields = ('name', 'state__name')

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'state')
    list_filter = ('state',)
    search_fields = ('name',)

@admin.register(Location)
class LocationAdmin(ImportExportModelAdmin):
    resource_class = LocationResource
    list_display = ('postal_code', 'name', 'settlement_type', 'municipality', 'city')
    list_filter = ('municipality__state', 'settlement_type')
    search_fields = ('postal_code', 'name', 'municipality__name')
    list_select_related = ('municipality', 'municipality__state', 'city')
    # Paginación ligera para que el admin no colapse con cientos de miles de registros
    list_per_page = 100