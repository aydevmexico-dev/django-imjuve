"""Vistas del Panel de Administración personalizado (independiente del admin nativo).

Solo accesible para roles SUPER y ESTATAL. Los Administradores Estatales ven únicamente
los datos de su `assigned_state` (mismo criterio territorial que `StateScopedAdminMixin`).
No modifica modelos ni admin: solo lee.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.forms import inlineformset_factory
from django.shortcuts import redirect
from django.urls import reverse
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
from django.views.generic import (
    CreateView, DetailView, ListView, TemplateView, UpdateView,
)

from programs.forms import EventForm, ProgramForm
from programs.models import Event, Images, Program, Requirements
from promotions.forms import CompanyForm, PromotionForm
from promotions.models import Company, Promotion
from tests.forms import ChoiceFormSet, QuestionForm, QuestionFormSet, TestForm
from tests.models import Question, Test, TestSession

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
        # La empresa ya tiene `state`: ESTATAL ve solo las suyas; SUPER, todas (incl. nacionales).
        qs = Company.objects.select_related("state")
        return qs.filter(state_id=self.scope_state_id) if self.scope_state_id else qs

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


class JovenExpedienteView(PanelAccessMixin, DetailView):
    """Expediente Digital de un joven en **solo lectura** para administradores.

    Aislamiento territorial (defensa IDOR): `get_queryset()` parte de los jóvenes ya acotados a
    la jurisdicción del administrador (`scoped_jovenes`). Si un ESTATAL solicita el `pk` de un
    joven de otro estado, el objeto no está en el queryset → 404 (no se filtra el recurso ni se
    confirma su existencia). El SUPER ve a cualquiera. No expone formularios de edición.
    """

    template_name = "panel/joven_expediente.html"
    context_object_name = "joven"
    active_nav = "encuestas"

    def get_queryset(self):
        return self.scoped_jovenes().select_related("assigned_state")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from records.views import build_saved_card  # presentación compartida con el portal joven

        joven = self.object
        record = getattr(joven, "digital_record", None)

        saved_cards = []
        if record:
            saved_qs = record.saved_items.select_related(
                "program__state", "program__municipality",
                "event__state", "event__municipality", "event__city",
                "promotion__state", "promotion__municipality", "promotion__city",
            )
            saved_cards = [c for c in (build_saved_card(i) for i in saved_qs) if c]
        ctx.update({
            "record": record,
            "youth_profile": getattr(joven, "youth_profile", None),
            "saved_cards": saved_cards,
            "historial": TestSession.objects.filter(user=joven).select_related("test"),
            "searches": record.searches.all()[:20] if record else [],
        })
        return ctx


# ============================================================================
# Altas y ediciones (CreateView / UpdateView) con aislamiento territorial
# ============================================================================
class PanelFormMixin(PanelAccessMixin):
    """Base para alta/edición del panel:

    * inyecta `user` al ModelForm (para que filtre la geografía por rol),
    * ancla el Estado del ESTATAL al guardar (defensa en profundidad, aunque el form ya
      bloquea el campo), y
    * arma el contexto que consume `panel/entity_form.html` (títulos, breadcrumb y las
      URLs de la cascada geográfica).
    """

    template_name = "panel/entity_form.html"
    entity_label = ""        # singular, p. ej. "Programa"
    entity_kicker = ""       # texto pequeño sobre el título
    list_url_name = ""       # ruta de la lista, p. ej. "panel:programas"
    extra_css = []           # hojas extra de sección (además de admin_forms.css)
    extra_js = []            # scripts extra de sección (además de admin_forms.js)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        obj = form.save(commit=False)
        if self.scope_state_id and hasattr(obj, "state_id"):
            obj.state_id = self.scope_state_id   # ancla irrenunciable para el ESTATAL
        obj.save()
        form.save_m2m()                           # Program.cities (M2M)
        self.object = obj
        messages.success(self.request, f"{self.entity_label} «{obj}» se guardó correctamente.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse(self.list_url_name)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        is_edit = getattr(self, "object", None) is not None
        ctx["is_edit"] = is_edit
        ctx["entity_label"] = self.entity_label
        ctx["entity_kicker"] = self.entity_kicker
        ctx["form_title"] = f"Editar {self.entity_label}" if is_edit else f"Nuevo · {self.entity_label}"
        ctx["list_url"] = reverse(self.list_url_name)
        # Endpoints de la cascada geográfica (los lee admin_forms.js).
        ctx["municipios_url"] = reverse("states:municipios")
        ctx["ciudades_url"] = reverse("states:ciudades")
        ctx["extra_css"] = self.extra_css
        ctx["extra_js"] = self.extra_js
        return ctx


class PanelInlineFormMixin(PanelFormMixin):
    """Alta/edición con formsets inline (Requisitos e Imágenes) y guardado transaccional.

    Cada subclase declara `inline_specs`. El padre y sus formsets se guardan dentro de un
    único `transaction.atomic()`: si algún formset falla, no queda ningún registro a medias.
    """

    inline_specs = []   # [{key, label, model, fk_name, fields, file?}]

    def _formset_class(self, spec):
        return inlineformset_factory(
            self.model, spec["model"], fields=spec["fields"],
            extra=1, can_delete=True, fk_name=spec["fk_name"],
        )

    def _build_inline_tabs(self, instance, data=None, files=None):
        tabs = []
        for spec in self.inline_specs:
            FormSet = self._formset_class(spec)
            tabs.append({
                "key": spec["key"],
                "label": spec["label"],
                "is_file": spec.get("file", False),
                "formset": FormSet(data, files, instance=instance, prefix=spec["key"]),
            })
        return tabs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if "inline_tabs" not in ctx:
            ctx["inline_tabs"] = self._build_inline_tabs(getattr(self, "object", None))
        return ctx

    def post(self, request, *args, **kwargs):
        # CreateView (sin pk) -> object None; UpdateView -> get_object() acotado (404 fuera de scope).
        self.object = self.get_object() if kwargs.get(self.pk_url_kwarg) else None
        form = self.get_form()
        tabs = self._build_inline_tabs(self.object, data=request.POST, files=request.FILES)
        if form.is_valid() and all(t["formset"].is_valid() for t in tabs):
            return self._save_all(form, tabs)
        return self.render_to_response(self.get_context_data(form=form, inline_tabs=tabs))

    def _save_all(self, form, tabs):
        with transaction.atomic():
            obj = form.save(commit=False)
            if self.scope_state_id and hasattr(obj, "state_id"):
                obj.state_id = self.scope_state_id   # ancla territorial del ESTATAL
            obj.save()
            form.save_m2m()
            for tab in tabs:
                tab["formset"].instance = obj
                tab["formset"].save()
        self.object = obj
        messages.success(self.request, f"{self.entity_label} «{obj}» se guardó correctamente.")
        return redirect(self.get_success_url())


# --- Programa ---
class _ProgramConfig(PanelInlineFormMixin):
    model = Program
    form_class = ProgramForm
    active_nav = "programas"
    entity_label = "Programa"
    entity_kicker = "Programas sociales"
    list_url_name = "panel:programas"
    inline_specs = [
        {"key": "req", "label": "Requisitos", "model": Requirements,
         "fk_name": "program", "fields": ["name"]},
        {"key": "img", "label": "Imágenes adicionales", "model": Images,
         "fk_name": "program", "fields": ["image"], "file": True},
    ]

    def get_queryset(self):
        return self.scoped_programs()


class ProgramCreateView(_ProgramConfig, CreateView):
    pass


class ProgramUpdateView(_ProgramConfig, UpdateView):
    pass


# --- Evento ---
class _EventConfig(PanelInlineFormMixin):
    model = Event
    form_class = EventForm
    active_nav = "programas"
    entity_label = "Evento"
    entity_kicker = "Programas y eventos"
    list_url_name = "panel:programas"
    inline_specs = [
        {"key": "req", "label": "Requisitos", "model": Requirements,
         "fk_name": "event", "fields": ["name"]},
        {"key": "img", "label": "Imágenes adicionales", "model": Images,
         "fk_name": "event", "fields": ["image"], "file": True},
    ]

    def get_queryset(self):
        return self.scoped_events()


class EventCreateView(_EventConfig, CreateView):
    pass


class EventUpdateView(_EventConfig, UpdateView):
    pass


# --- Empresa (Company) ---
class _CompanyConfig(PanelFormMixin):
    model = Company
    form_class = CompanyForm
    active_nav = "descuentos"
    entity_label = "Empresa"
    entity_kicker = "Red de beneficios"
    list_url_name = "panel:descuentos"
    extra_css = ["css/admin_benefits.css"]
    extra_js = ["js/admin_benefits.js"]

    def get_queryset(self):
        return self.scoped_companies()


class CompanyCreateView(_CompanyConfig, CreateView):
    pass


class CompanyUpdateView(_CompanyConfig, UpdateView):
    pass


# --- Descuento (Promotion) ---
class _PromotionConfig(PanelFormMixin):
    model = Promotion
    form_class = PromotionForm
    active_nav = "descuentos"
    entity_label = "Promoción"
    entity_kicker = "Descuentos y beneficios"
    list_url_name = "panel:descuentos"
    extra_css = ["css/admin_benefits.css"]
    extra_js = ["js/admin_benefits.js"]

    def get_queryset(self):
        return self.scoped_promotions()


class PromotionCreateView(_PromotionConfig, CreateView):
    pass


class PromotionUpdateView(_PromotionConfig, UpdateView):
    pass


# --- Encuesta (Test) con preguntas y opciones anidadas ---
class EncuestaFormMixin(PanelFormMixin):
    """Alta/edición UNIFICADA de una encuesta: el `Test`, sus `Question` (formset
    externo) y, en cascada, las `Choice` de cada pregunta de Opción Múltiple
    (formset interno anidado), todo en una sola pantalla y un solo guardado
    transaccional.

    El anidamiento se resuelve con un prefijo de formset por índice de pregunta:
    la pregunta `i` lleva sus opciones bajo el prefijo ``choices-i``. Las plantillas
    vacías para clonar en el cliente usan el token ``__qprefix__`` (pregunta) y el
    nativo ``__prefix__`` (opción), tokens distintos que `admin_surveys.js`
    reemplaza por separado al duplicar filas.
    """

    template_name = "panel/encuesta_form.html"
    model = Test
    form_class = TestForm
    active_nav = "encuestas"
    entity_label = "Encuesta"
    entity_kicker = "Encuestas y tests"
    list_url_name = "panel:encuestas"
    extra_css = ["css/admin_surveys.css"]
    extra_js = ["js/admin_surveys.js"]

    def get_queryset(self):
        # Edición acotada ESTRICTA por estado: el ESTATAL no edita tests nacionales
        # (de poder hacerlo, el guardado los re-anclaría a su estado por error).
        qs = Test.objects.all()
        if self.scope_state_id:
            qs = qs.filter(state_id=self.scope_state_id)
        return qs

    @staticmethod
    def _choice_prefix(index):
        return f"choices-{index}"

    def _build_pairs(self, test, data=None):
        """Construye el formset de preguntas y, por cada pregunta, su formset de
        opciones. Devuelve `(question_formset, [(qform, choice_formset), ...])`."""
        q_formset = QuestionFormSet(data, instance=test, prefix="questions")
        pairs = []
        for i, qform in enumerate(q_formset.forms):
            cf = ChoiceFormSet(data, instance=qform.instance, prefix=self._choice_prefix(i))
            qform.choice_formset = cf          # lo consume la plantilla
            pairs.append((qform, cf))
        return q_formset, pairs

    @staticmethod
    def _is_mc(qform):
        cd = getattr(qform, "cleaned_data", None) or {}
        return cd.get("question_type") == Question.MULTIPLE_CHOICE and not cd.get("DELETE")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if "q_formset" not in ctx:
            q_formset, pairs = self._build_pairs(getattr(self, "object", None))
            ctx["q_formset"] = q_formset
            ctx["pairs"] = pairs
        # Plantillas vacías para que admin_surveys.js clone filas en el cliente.
        ctx["empty_question_form"] = QuestionForm(prefix="questions-__qprefix__")
        ctx["empty_choice_formset"] = ChoiceFormSet(prefix="choices-__qprefix__")
        return ctx

    def post(self, request, *args, **kwargs):
        # CreateView -> object None; UpdateView -> get_object() acotado (404 fuera de scope).
        self.object = self.get_object() if kwargs.get(self.pk_url_kwarg) else None
        form = self.get_form()
        q_formset, pairs = self._build_pairs(self.object, data=request.POST)

        form_ok = form.is_valid()
        q_ok = q_formset.is_valid()
        # Solo validamos las opciones de las preguntas MC que NO se van a borrar.
        choices_ok = True
        if q_ok:
            for qform, cf in pairs:
                if self._is_mc(qform) and not cf.is_valid():
                    choices_ok = False

        if form_ok and q_ok and choices_ok:
            return self._save_survey(form, q_formset, pairs)
        return self.render_to_response(
            self.get_context_data(form=form, q_formset=q_formset, pairs=pairs)
        )

    def _save_survey(self, form, q_formset, pairs):
        with transaction.atomic():
            test = form.save(commit=False)
            if self.scope_state_id and hasattr(test, "state_id"):
                test.state_id = self.scope_state_id   # ancla territorial del ESTATAL
            test.save()
            form.save_m2m()

            q_formset.instance = test
            q_formset.save()   # crea/actualiza/elimina preguntas (las MC->TXT incluidas)

            for qform, cf in pairs:
                cd = getattr(qform, "cleaned_data", None) or {}
                question = qform.instance
                if cd.get("DELETE") or question.pk is None:
                    continue   # pregunta borrada o fila vacía descartada por Django
                if question.question_type == Question.MULTIPLE_CHOICE:
                    cf.instance = question
                    cf.save()
                else:
                    # Pregunta de Texto Libre: no debe conservar opciones colgando.
                    question.choices.all().delete()

        self.object = test
        messages.success(self.request, f"Encuesta «{test}» se guardó correctamente.")
        return redirect(self.get_success_url())


class EncuestaCreateView(EncuestaFormMixin, CreateView):
    pass


class EncuestaUpdateView(EncuestaFormMixin, UpdateView):
    pass
