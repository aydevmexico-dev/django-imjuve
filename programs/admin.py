from django.contrib import admin
from accounts.admin import StateScopedAdminMixin
from .models import Program, Event, Requirements, Images

class RequirementsInline(admin.TabularInline):
    readonly_fields = ('program', 'event')
    model = Requirements
    extra = 1

class ImagesInline(admin.TabularInline):
    readonly_fields = ('program', 'event')
    model = Images
    extra = 1

@admin.register(Program)
class ProgramAdmin(StateScopedAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'state', 'municipality', 'start_date', 'end_date')
    search_fields = ('name',)
    inlines = [RequirementsInline, ImagesInline]
    list_filter = ('state', 'municipality')
    fieldsets = (
        (None, {
            'fields': ('name', 'state', 'municipality', 'start_date', 'end_date', 'image','organizing_institution','description')
        }),
    )

@admin.register(Event)
class EventAdmin(StateScopedAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'state', 'municipality', 'city', 'start_date', 'end_date')
    search_fields = ('name',)
    inlines = [RequirementsInline, ImagesInline]
    list_filter = ('state', 'municipality', 'city')
    fieldsets = (
        (None, {
            'fields': ('name', 'state', 'municipality', 'city', 'start_date', 'end_date', 'image', 'headquarters', 'organizing_institution', 'description')
        }),
    )

# Los requisitos e imágenes se editan dentro de Programa/Evento (inlines, ya acotados
# por estado). La vista independiente queda reservada a superusuarios.
class SuperuserOnlyAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Requirements)
class RequirementsAdmin(SuperuserOnlyAdmin):
    list_display = ('name', 'program', 'event')
    search_fields = ('name',)
    list_filter = ('program', 'event')

@admin.register(Images)
class ImagesAdmin(SuperuserOnlyAdmin):
    list_display = ('program', 'event', 'image')
    search_fields = ('program__name', 'event__name')
    list_filter = ('program', 'event')

