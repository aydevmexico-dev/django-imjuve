from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group

from states.models import City, Municipality, State

from .models import CustomUser, YouthProfile

ESTATAL_GROUP_NAME = "Administradores Estatales"


# --- Formularios adaptados al login por correo ---

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("email",)


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = CustomUser
        fields = "__all__"


# --- Mixin de alcance territorial ---

class StateScopedAdminMixin:
    """
    Limita un ModelAdmin al `assigned_state` del Administrador Estatal.

    Asume que el modelo tiene una FK directa a State (configurable vía
    `state_field_name`). Los superusuarios no se ven afectados.

    Debe declararse ANTES de admin.ModelAdmin en la herencia para que
    super() encadene correctamente hacia ModelAdmin.
    """

    state_field_name = "state"

    def _is_estatal(self, request):
        u = request.user
        return (
            u.is_active
            and u.is_staff
            and not u.is_superuser
            and getattr(u, "role", None) == CustomUser.Role.ESTATAL
            and getattr(u, "assigned_state_id", None) is not None
        )

    def _obj_in_scope(self, request, obj):
        if obj is None:
            return True
        return (
            getattr(obj, f"{self.state_field_name}_id", None)
            == request.user.assigned_state_id
        )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self._is_estatal(request):
            qs = qs.filter(
                **{f"{self.state_field_name}_id": request.user.assigned_state_id}
            )
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if self._is_estatal(request):
            sid = request.user.assigned_state_id
            if db_field.name == self.state_field_name:
                kwargs["queryset"] = State.objects.filter(pk=sid)
                kwargs["initial"] = sid
            elif db_field.name == "municipality":
                kwargs["queryset"] = Municipality.objects.filter(state_id=sid)
            elif db_field.name == "city":
                kwargs["queryset"] = City.objects.filter(state_id=sid)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if self._is_estatal(request) and db_field.name == "cities":
            kwargs["queryset"] = City.objects.filter(
                state_id=request.user.assigned_state_id
            )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # Defensa en profundidad: aun con un POST manipulado, el registro
        # se ancla al estado del administrador.
        if self._is_estatal(request):
            setattr(obj, f"{self.state_field_name}_id", request.user.assigned_state_id)
        super().save_model(request, obj, form, change)

    def has_view_permission(self, request, obj=None):
        base = super().has_view_permission(request, obj)
        if base and self._is_estatal(request):
            return self._obj_in_scope(request, obj)
        return base

    def has_change_permission(self, request, obj=None):
        base = super().has_change_permission(request, obj)
        if base and self._is_estatal(request):
            return self._obj_in_scope(request, obj)
        return base

    def has_delete_permission(self, request, obj=None):
        base = super().has_delete_permission(request, obj)
        if base and self._is_estatal(request):
            return self._obj_in_scope(request, obj)
        return base


# --- Admin de Usuarios (solo superusuarios) ---

class YouthProfileInline(admin.StackedInline):
    model = YouthProfile
    can_delete = False
    extra = 0
    verbose_name_plural = "Perfil de Joven"


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser

    ordering = ("email",)
    list_display = ("email", "role", "assigned_state", "is_staff", "is_active")
    list_filter = ("role", "assigned_state", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")
    inlines = [YouthProfileInline]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Información personal", {"fields": ("first_name", "last_name")}),
        ("Rol y alcance", {"fields": ("role", "assigned_state")}),
        (
            "Permisos",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Fechas importantes", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "role", "assigned_state"),
            },
        ),
    )

    # Solo los superusuarios gestionan cuentas (evita escalada de privilegios).
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

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Sincroniza la pertenencia al grupo Estatal con el rol.
        group = Group.objects.filter(name=ESTATAL_GROUP_NAME).first()
        if group is not None:
            if obj.role == CustomUser.Role.ESTATAL:
                obj.groups.add(group)
            else:
                obj.groups.remove(group)
