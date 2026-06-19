"""Vistas del Panel de Administración personalizado (independiente del admin nativo).

Solo accesible para roles SUPER y ESTATAL. Los Administradores Estatales ven únicamente
los datos de su `assigned_state` (mismo criterio territorial que `StateScopedAdminMixin`).
No modifica modelos ni admin: solo lee.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

MESES_ABREV = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _ultimos_meses(today, n=6):
    """Lista de (año, mes) para los últimos `n` meses, del más antiguo al actual."""
    pares, y, m = [], today.year, today.month
    for _ in range(n):
        pares.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(pares))
from django.views.generic import DetailView, ListView, TemplateView

from programs.models import Event, Program
from promotions.models import Company, Promotion
from tests.models import Test, TestSession

CustomUser = get_user_model()

# Rutas de scope territorial reutilizadas en varias consultas.
JOVEN_STATE_PATH = "youth_profile__residence_location__municipality__state_id"
SESION_STATE_PATH = "user__youth_profile__residence_location__municipality__state_id"


class PanelAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Garantiza login + rol administrativo (SUPER/ESTATAL). Bloquea a los GENERAL."""

    active_nav = ""  # lo sobreescribe cada vista para marcar el item activo del sidebar

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.role in {
            CustomUser.Role.SUPER,
            CustomUser.Role.ESTATAL,
        }

    def handle_no_permission(self):
        # Un Joven autenticado no debe entrar: 403 (no tiene sentido mandarlo al login).
        if self.request.user.is_authenticated:
            raise PermissionDenied("No tienes acceso al panel de administración.")
        return super().handle_no_permission()

    @property
    def scope_state_id(self):
        """ID del estado asignado si es ESTATAL; None para SUPER (alcance nacional)."""
        user = self.request.user
        return user.assigned_state_id if user.role == CustomUser.Role.ESTATAL else None

    # --- Querysets ya acotados al territorio del administrador ---
    def scoped_jovenes(self):
        qs = CustomUser.objects.filter(role=CustomUser.Role.GENERAL)
        if self.scope_state_id:
            qs = qs.filter(**{JOVEN_STATE_PATH: self.scope_state_id})
        return qs

    def scoped_programs(self):
        qs = Program.objects.select_related("state", "municipality")
        return qs.filter(state_id=self.scope_state_id) if self.scope_state_id else qs

    def scoped_events(self):
        qs = Event.objects.select_related("state", "municipality", "city")
        return qs.filter(state_id=self.scope_state_id) if self.scope_state_id else qs

    def scoped_promotions(self):
        qs = Promotion.objects.select_related("company", "state", "municipality", "city")
        return qs.filter(state_id=self.scope_state_id) if self.scope_state_id else qs

    def scoped_companies(self):
        if self.scope_state_id:
            return Company.objects.filter(promotions__state_id=self.scope_state_id).distinct()
        return Company.objects.all()

    def scoped_tests(self):
        qs = Test.objects.select_related("state")
        if self.scope_state_id:
            # Encuestas de su estado + las nacionales (state nulo) que también le aplican.
            qs = qs.filter(Q(state_id=self.scope_state_id) | Q(state__isnull=True))
        return qs

    def scoped_sessions(self):
        qs = TestSession.objects.select_related(
            "user", "test", "user__youth_profile__residence_location__municipality__state"
        )
        if self.scope_state_id:
            qs = qs.filter(**{SESION_STATE_PATH: self.scope_state_id})
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["active_nav"] = self.active_nav
        ctx["role_label"] = user.get_role_display()
        ctx["is_estatal"] = user.role == CustomUser.Role.ESTATAL
        ctx["scope_label"] = (
            user.assigned_state.name
            if (user.role == CustomUser.Role.ESTATAL and user.assigned_state_id)
            else "Nacional"
        )
        return ctx


class DashboardIndexView(PanelAccessMixin, TemplateView):
    template_name = "panel/dashboard_index.html"
    active_nav = "dashboard"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()

        jovenes = self.scoped_jovenes()
        programs = self.scoped_programs()
        events = self.scoped_events()
        promotions = self.scoped_promotions()
        tests = self.scoped_tests()
        sessions = self.scoped_sessions()

        programas_vigentes = programs.filter(Q(end_date__gte=today) | Q(end_date__isnull=True))
        eventos_proximos = events.filter(start_date__gte=today)
        promos_activas = promotions.filter(
            Q(start_date__lte=today) | Q(start_date__isnull=True),
            Q(end_date__gte=today) | Q(end_date__isnull=True),
        )
        tests_activos = tests.filter(is_active=True)

        n_programas = programas_vigentes.count()
        n_eventos = eventos_proximos.count()
        n_promos = promos_activas.count()
        n_tests = tests_activos.count()
        n_sesiones = sessions.count()
        n_jovenes = jovenes.count()

        ctx["kpis"] = [
            {"key": "jovenes", "label": "Jóvenes registrados", "value": n_jovenes,
             "sub": "Perfiles activos en tu región" if self.scope_state_id else "A nivel nacional"},
            {"key": "sesiones", "label": "Encuestas completadas", "value": n_sesiones,
             "sub": "Sesiones de test resueltas"},
            {"key": "programas", "label": "Programas vigentes", "value": n_programas,
             "sub": "Convocatorias abiertas"},
            {"key": "eventos", "label": "Eventos próximos", "value": n_eventos,
             "sub": "Con fecha por venir"},
            {"key": "promos", "label": "Promociones activas", "value": n_promos,
             "sub": "Beneficios vigentes"},
            {"key": "encuestas", "label": "Encuestas activas", "value": n_tests,
             "sub": "Disponibles para responder"},
        ]

        # Donut: composición por módulo (categórico).
        chart = [
            {"label": "Programas", "value": programs.count()},
            {"label": "Eventos", "value": events.count()},
            {"label": "Promociones", "value": promotions.count()},
            {"label": "Encuestas", "value": tests.count()},
            {"label": "Sesiones", "value": sessions.count()},
        ]
        ctx["chart"] = chart
        ctx["chart_total"] = sum(c["value"] for c in chart)

        # Tendencia: sesiones de encuesta por mes (últimos 6 meses, dato temporal real).
        meses = _ultimos_meses(today, 6)
        por_mes = (
            sessions.annotate(mth=TruncMonth("completed_at"))
            .values("mth").annotate(c=Count("id"))
        )
        conteo = {(r["mth"].year, r["mth"].month): r["c"] for r in por_mes if r["mth"]}
        trend = [{"label": MESES_ABREV[m], "value": conteo.get((y, m), 0)} for (y, m) in meses]
        ctx["trend"] = trend
        ctx["trend_max"] = max([t["value"] for t in trend] + [1])
        ctx["trend_total"] = sum(t["value"] for t in trend)

        ctx["recent_sessions"] = sessions.order_by("-completed_at")[:12]
        ctx["recent_jovenes"] = jovenes.order_by("-date_joined")[:6]
        return ctx


class ProgramasEventosView(PanelAccessMixin, TemplateView):
    template_name = "panel/programas.html"
    active_nav = "programas"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["programas"] = self.scoped_programs().order_by("-start_date")[:50]
        ctx["eventos"] = self.scoped_events().order_by("-start_date")[:50]
        ctx["today"] = timezone.localdate()
        return ctx


class DescuentosView(PanelAccessMixin, TemplateView):
    template_name = "panel/descuentos.html"
    active_nav = "descuentos"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["promociones"] = self.scoped_promotions().order_by("company__name", "name")[:60]
        ctx["empresas"] = self.scoped_companies().order_by("name")
        ctx["today"] = timezone.localdate()
        return ctx


class EncuestasView(PanelAccessMixin, ListView):
    template_name = "panel/encuestas.html"
    context_object_name = "tests"
    active_nav = "encuestas"

    def get_queryset(self):
        return (
            self.scoped_tests()
            .annotate(num_preguntas=Count("questions", distinct=True),
                      num_sesiones=Count("sessions", distinct=True))
            .order_by("-is_active", "name")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sesiones"] = self.scoped_sessions().order_by("-completed_at")[:25]
        return ctx


class SesionDetalleView(PanelAccessMixin, DetailView):
    template_name = "panel/sesion_detalle.html"
    context_object_name = "sesion"
    active_nav = "encuestas"

    def get_queryset(self):
        # Acotado al territorio: una sesión fuera de su estado devuelve 404 para el ESTATAL.
        return self.scoped_sessions().prefetch_related(
            "answers__question", "answers__chosen_choice"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # La región del joven se resuelve aquí (no en plantilla) por si no tiene perfil.
        region = "—"
        try:
            loc = self.object.user.youth_profile.residence_location
            if loc:
                region = loc.municipality.state.name
        except ObjectDoesNotExist:
            pass
        ctx["region"] = region
        return ctx
