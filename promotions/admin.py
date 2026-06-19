from django.contrib import admin
from accounts.admin import StateScopedAdminMixin
from .models import Promotion, Company, PromotionImage

class PromotionInline(admin.TabularInline):
    model = Promotion
    extra = 1

class PromotionImageInline(admin.TabularInline):
    model = PromotionImage
    extra = 1

# Company no tiene estado (catálogo compartido) y su inline expondría promociones
# de todos los estados; queda reservada a superusuarios. Los Estatales siguen
# eligiendo la empresa desde el desplegable al crear una Promoción.
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    list_filter = ('name',)
    inlines = [PromotionInline]

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

@admin.register(Promotion)
class PromotionAdmin(StateScopedAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'company', 'state', 'municipality', 'city', 'start_date', 'end_date')
    search_fields = ('name', 'company__name')
    list_filter = ('company', 'state', 'municipality', 'city')
    inlines = [PromotionImageInline]


