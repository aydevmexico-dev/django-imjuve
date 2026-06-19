from django.contrib import admin
from accounts.admin import StateScopedAdminMixin  
from .models import Test, Question, Choice, TestSession, Answer

# =====================================================================
# 1. GESTIÓN Y ALTA DE ENCUESTAS (Para SuperAdmins y Estatales)
# =====================================================================

class ChoiceInline(admin.TabularInline):
    """Permite añadir opciones directamente dentro de la pregunta."""
    model = Choice
    extra = 3


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text_preview', 'test', 'question_type')
    list_filter = ('test', 'question_type')
    search_fields = ('text', 'test__name')
    inlines = [ChoiceInline]

    def text_preview(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
    text_preview.short_description = "Pregunta"


class QuestionInline(admin.TabularInline):
    """Permite añadir preguntas directamente al crear o editar un Test."""
    model = Question
    extra = 1
    show_change_link = True


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    """Aquí los administradores dan de alta los Tests y definen su segmentación."""
    list_display = ('name', 'organizing_institution', 'state', 'date_start', 'date_end', 'is_active')
    list_filter = ('is_active', 'state', 'date_start')
    search_fields = ('name', 'organizing_institution')
    # Buscables (Select2): manejan los ~2458 municipios sin cargar todo en un <select>.
    # Funciona porque State/Municipality/City Admin definen search_fields.
    autocomplete_fields = ('state', 'municipality', 'city')
    inlines = [QuestionInline]
    fieldsets = (
        ("Datos generales", {
            "fields": ('name', 'organizing_institution', 'is_active'),
        }),
        ("Vigencia", {
            "fields": ('date_start', 'date_end'),
        }),
        ("Segmentación por edad", {
            "fields": ('age_min', 'age_max'),
            "description": "Opcional. Vacío = sin filtro de edad.",
        }),
        ("Segmentación territorial", {
            "fields": ('state', 'municipality', 'city'),
            "description": "Opcional. Vacío = alcance nacional. "
                           "Municipio/Ciudad deben pertenecer al Estado seleccionado.",
        }),
    )


# =====================================================================
# 2. SECCIÓN DE RESPUESTAS Y ESTADÍSTICAS (Con Filtro Territorial)
# =====================================================================

class AnswerInline(admin.TabularInline):
    """Muestra el examen contestado. Es de solo lectura para evitar alteraciones."""
    model = Answer
    extra = 0
    readonly_fields = ('question', 'text_answer', 'chosen_choice')
    can_delete = False


@admin.register(TestSession)
class TestSessionAdmin(StateScopedAdminMixin, admin.ModelAdmin):
    """
    Panel para auditar intentos. 
    Usa el Mixin para que el Admin Estatal solo vea alumnos de su propio estado.
    """
    list_display = ('user_email', 'user_state', 'test', 'completed_at', 'score')
    list_filter = ('test', 'completed_at')
    search_fields = ('user__email', 'test__name')
    readonly_fields = ('user', 'test', 'completed_at', 'score')
    inlines = [AnswerInline]

    # Ajustamos el campo que el Mixin usará para filtrar.
    # La relación al estado está en el Perfil del Joven, y Location NO tiene FK directa
    # a State: la ruta correcta pasa por municipality (Location -> Municipality -> State).
    state_field_name = "user__youth_profile__residence_location__municipality__state"

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "Usuario (Email)"

    def user_state(self, obj):
        # Muestra el estado del joven en la tabla si tiene perfil e información geográfica.
        if hasattr(obj.user, 'youth_profile') and obj.user.youth_profile.residence_location:
            return obj.user.youth_profile.residence_location.municipality.state.name
        return "No asignado"
    user_state.short_description = "Estado del Joven"

    def get_queryset(self, request):
        """
        Sobreescribimos para optimizar las consultas (evitar el problema N+1)
        y asegurar que el Mixin pueda evaluar el campo anidado correctamente.
        """
        qs = super().get_queryset(request)
        return qs.select_related('user__youth_profile__residence_location__municipality__state', 'test')