"""Portal de Jóvenes (rol GENERAL) — vistas de SOLO consulta.

Espejo *invertido* del panel administrativo (`core/panel_views.py`): aquí el contenido del
IMJUVE se **consume**, nunca se edita. La única escritura permitida es responder una encuesta
(`TestResponderView` crea `TestSession` + `Answer`).

Filtros aplicados a Programas/Eventos/Descuentos:
  · Vigencia (estricto): `end_date >= hoy` o sin fecha de fin.
  · Edad (estricto, solo Programas): la edad del joven debe caer en `age_from`–`age_to`.
  · Territorio (prioritización): primero su Estado, luego los nacionales, luego el resto.

El Estado del joven se estima por IP (`core.services.detect_youth_state`) con respaldo a su
Estado de residencia. Los administradores (SUPER/ESTATAL) entran en **modo vista previa**: no se
les bloquea ni se rompe el flujo aunque no tengan `youth_profile`.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Case, IntegerField, Q, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from programs.models import Event, Program
from promotions.models import Promotion
from states.models import State
from tests.models import Answer, Question, Test, TestSession, available_tests_for

from core.geodata import centroid_for
from core.services import detect_youth_state

CustomUser = get_user_model()

MAP_LIMIT = 200   # tope defensivo de pines por consulta


# ---------------------------------------------------------------------------
# Helpers de presentación (etiquetas legibles, sin lógica de negocio)
# ---------------------------------------------------------------------------
def _date_label(start, end):
    if start and end:
        return f"Del {start:%d/%m/%Y} al {end:%d/%m/%Y}"
    if end:
        return f"Hasta {end:%d/%m/%Y}"
    if start:
        return f"Desde {start:%d/%m/%Y}"
    return "Vigencia abierta"


def _location_label(state, municipality=None, city=None):
    parts = [obj.name for obj in (city, municipality, state) if obj]
    return ", ".join(parts) if parts else "Nacional"


def _age_label(age_from, age_to):
    if age_from and age_to:
        return f"{age_from}–{age_to} años"
    if age_from:
        return f"Desde {age_from} años"
    if age_to:
        return f"Hasta {age_to} años"
    return "Todas las edades"


def build_response_form(test, data=None):
    """Form dinámico de respuesta: un campo por pregunta (Textarea para TXT, radios para MC)."""
    fields = {}
    for q in test.questions.all():
        name = f"q_{q.id}"
        if q.question_type == Question.MULTIPLE_CHOICE:
            fields[name] = forms.ModelChoiceField(
                queryset=q.choices.all(), label=q.text, required=False,
                widget=forms.RadioSelect, empty_label=None,
            )
        else:
            fields[name] = forms.CharField(
                label=q.text, required=False,
                widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea",
                                             "placeholder": "Escribe tu respuesta…"}),
            )
    form_class = type("TestResponseForm", (forms.Form,), fields)
    return form_class(data) if data is not None else form_class()


# ---------------------------------------------------------------------------
# Mixin de acceso + filtrado
# ---------------------------------------------------------------------------
class YouthAccessMixin(LoginRequiredMixin):
    """Exige login. Permite a GENERAL (experiencia plena) y a SUPER/ESTATAL (vista previa).

    No bloquea a los administradores: el requisito pide que puedan previsualizar el portal sin
    que la geolocalización por IP ni los filtros personales rompan la página.
    """

    active_nav = ""

    @property
    def is_preview(self):
        return self.request.user.role in {CustomUser.Role.SUPER, CustomUser.Role.ESTATAL}

    @property
    def youth_profile(self):
        if not hasattr(self, "_youth_profile"):
            try:
                self._youth_profile = self.request.user.youth_profile
            except ObjectDoesNotExist:
                self._youth_profile = None
        return self._youth_profile

    def _resolve_state(self):
        if not hasattr(self, "_eff_state"):
            user = self.request.user
            if self.is_preview:
                # El admin no se geolocaliza: usa su estado asignado (ESTATAL) o nada (SUPER).
                self._eff_state = (user.assigned_state_id, "asignado")
            else:
                self._eff_state = detect_youth_state(self.request, user)
        return self._eff_state

    @property
    def effective_state_id(self):
        return self._resolve_state()[0]

    @property
    def effective_state_source(self):
        return self._resolve_state()[1]

    @property
    def user_age(self):
        if not hasattr(self, "_user_age"):
            prof = self.youth_profile
            birthdate = prof.birthdate if prof else None
            self._user_age = Test._calculate_age(birthdate) if birthdate else None
        return self._user_age

    # --- Filtros reutilizables ---
    def vigentes(self, qs):
        today = timezone.localdate()
        return qs.filter(Q(end_date__gte=today) | Q(end_date__isnull=True))

    def age_filter_program(self, qs):
        """Solo aplica a Programas (Eventos/Promociones no tienen rango de edad)."""
        age = self.user_age
        if age is None:
            return qs   # sin fecha de nacimiento: no ocultamos nada
        return qs.filter(
            Q(age_from__isnull=True) | Q(age_from__lte=age),
            Q(age_to__isnull=True) | Q(age_to__gte=age),
        )

    def prioritize(self, qs):
        """Anota `prio` (0 = su estado, 1 = nacional, 2 = resto). Nunca excluye registros."""
        sid = self.effective_state_id
        if sid:
            whens = [When(state_id=sid, then=0), When(state__isnull=True, then=1)]
            default = 2
        else:
            whens = [When(state__isnull=True, then=0)]
            default = 1
        return qs.annotate(prio=Case(*whens, default=default, output_field=IntegerField()))

    def _card(self, *, kind, detail_url, image, title, subtitle,
              state, municipality=None, city=None, start=None, end=None):
        sid = self.effective_state_id
        return {
            "kind": kind,
            "detail_url": detail_url,
            "image_url": image.url if image else None,
            "title": title,
            "subtitle": subtitle,
            "location": _location_label(state, municipality, city),
            "date_label": _date_label(start, end),
            "is_local": bool(sid and state and state.id == sid),
            "is_national": state is None,
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sid = self.effective_state_id
        region = "Nacional"
        if sid:
            st = State.objects.filter(id=sid).first()
            region = st.name.title() if st else "Nacional"
        ctx.update({
            "active_nav": self.active_nav,
            "is_preview": self.is_preview,
            "region_label": region,
            "region_source": self.effective_state_source,
            "has_state": bool(sid),
            "user_age": self.user_age,
            "role_label": self.request.user.get_role_display(),
        })
        return ctx


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
class YouthDashboardView(YouthAccessMixin, TemplateView):
    template_name = "youth/dashboard.html"
    active_nav = "dashboard"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        programas = self.age_filter_program(self.vigentes(Program.objects.all()))
        eventos = self.vigentes(Event.objects.all())
        descuentos = self.vigentes(Promotion.objects.all())
        encuestas = available_tests_for(self.request.user)
        ctx["kpis"] = [
            {"key": "programas", "label": "Programas para ti", "value": programas.count(),
             "sub": "Convocatorias vigentes a tu perfil"},
            {"key": "eventos", "label": "Eventos próximos", "value": eventos.count(),
             "sub": "Actividades con fecha por venir"},
            {"key": "promos", "label": "Descuentos vigentes", "value": descuentos.count(),
             "sub": "Beneficios para jóvenes"},
            {"key": "encuestas", "label": "Encuestas disponibles", "value": len(encuestas),
             "sub": "Tu opinión cuenta"},
        ]
        ctx["map_url"] = reverse("youth:mapa_data")
        return ctx


# ---------------------------------------------------------------------------
# Listados (ListView, solo lectura)
# ---------------------------------------------------------------------------
class ProgramasListView(YouthAccessMixin, ListView):
    model = Program
    active_nav = "programas"
    template_name = "youth/programas.html"
    context_object_name = "programas"

    def get_queryset(self):
        qs = Program.objects.select_related("state", "municipality")
        qs = self.age_filter_program(self.vigentes(qs))
        return self.prioritize(qs).order_by("prio", "-start_date", "name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cards"] = [
            self._card(
                kind="programa", detail_url=reverse("youth:programa_detalle", args=[p.pk]),
                image=p.image, title=p.name,
                subtitle=p.organizing_institution or "Programa social",
                state=p.state, municipality=p.municipality,
                start=p.start_date, end=p.end_date,
            )
            for p in ctx["programas"]
        ]
        return ctx


class EventosListView(YouthAccessMixin, ListView):
    model = Event
    active_nav = "eventos"
    template_name = "youth/eventos.html"
    context_object_name = "eventos"

    def get_queryset(self):
        qs = Event.objects.select_related("state", "municipality", "city")
        return self.prioritize(self.vigentes(qs)).order_by("prio", "start_date", "name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cards"] = [
            self._card(
                kind="evento", detail_url=reverse("youth:evento_detalle", args=[e.pk]),
                image=e.image, title=e.name,
                subtitle=e.headquarters or e.organizing_institution or "Evento",
                state=e.state, municipality=e.municipality, city=e.city,
                start=e.start_date, end=e.end_date,
            )
            for e in ctx["eventos"]
        ]
        return ctx


class DescuentosListView(YouthAccessMixin, ListView):
    model = Promotion
    active_nav = "descuentos"
    template_name = "youth/descuentos.html"
    context_object_name = "promociones"

    def get_queryset(self):
        qs = Promotion.objects.select_related("company", "state", "municipality", "city")
        return self.prioritize(self.vigentes(qs)).order_by("prio", "name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cards = []
        for p in ctx["promociones"]:
            image = p.image or (p.company.logo if p.company else None)
            cards.append(self._card(
                kind="descuento", detail_url=reverse("youth:descuento_detalle", args=[p.pk]),
                image=image, title=p.name,
                subtitle=p.company.name if p.company else "Promoción",
                state=p.state, municipality=p.municipality, city=p.city,
                start=p.start_date, end=p.end_date,
            ))
        ctx["cards"] = cards
        return ctx


# ---------------------------------------------------------------------------
# Detalle bajo demanda (DetailView; fragmento si la petición es AJAX)
# ---------------------------------------------------------------------------
class _YouthDetailBase(YouthAccessMixin, DetailView):
    context_object_name = "obj"

    def get_template_names(self):
        # AJAX (click en tarjeta) -> solo el fragmento del modal; navegación directa -> página.
        if self.request.headers.get("x-requested-with"):
            return ["youth/_detail_modal.html"]
        return ["youth/detalle.html"]

    # kind (en minúsculas, como en records.SAVED_KINDS) -> campo FK en SavedItem.
    _fav_field = {"programa": "program", "evento": "event", "descuento": "promotion"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        detail = self.build_detail(self.object)
        ctx["detail"] = detail

        # Estado inicial del botón "Guardar" (solo el joven tiene expediente).
        fav_kind = detail["kind"].lower()
        ctx["fav_kind"] = fav_kind
        ctx["is_saved"] = False
        user = self.request.user
        if user.role == CustomUser.Role.GENERAL:
            from records.models import SavedItem  # import local: evita ciclo en el arranque
            field = self._fav_field.get(fav_kind)
            if field:
                ctx["is_saved"] = SavedItem.objects.filter(
                    record__user=user, **{field: self.object}
                ).exists()
        return ctx


class ProgramaDetailView(_YouthDetailBase):
    active_nav = "programas"

    def get_queryset(self):
        return Program.objects.select_related("state", "municipality").prefetch_related(
            "requirements", "images")

    def build_detail(self, p):
        return {
            "kind": "Programa", "title": p.name,
            "image_url": p.image.url if p.image else None,
            "description": p.description,
            "institution": p.organizing_institution,
            "sede": None,
            "location": _location_label(p.state, p.municipality),
            "date_label": _date_label(p.start_date, p.end_date),
            "age_label": _age_label(p.age_from, p.age_to),
            "requirements": [r.name for r in p.requirements.all()],
            "requirements_text": None,
            "extra_images": [i.image.url for i in p.images.all() if i.image],
            "external_url": p.access_link,
            "external_label": "Ir a la convocatoria",
            "back_url": reverse("youth:programas"),
        }


class EventoDetailView(_YouthDetailBase):
    active_nav = "eventos"

    def get_queryset(self):
        return Event.objects.select_related("state", "municipality", "city").prefetch_related(
            "requirements", "images")

    def build_detail(self, e):
        return {
            "kind": "Evento", "title": e.name,
            "image_url": e.image.url if e.image else None,
            "description": e.description,
            "institution": e.organizing_institution,
            "sede": e.headquarters,
            "location": _location_label(e.state, e.municipality, e.city),
            "date_label": _date_label(e.start_date, e.end_date),
            "age_label": None,
            "requirements": [r.name for r in e.requirements.all()],
            "requirements_text": None,
            "extra_images": [i.image.url for i in e.images.all() if i.image],
            "external_url": None,
            "external_label": None,
            "back_url": reverse("youth:eventos"),
        }


class DescuentoDetailView(_YouthDetailBase):
    active_nav = "descuentos"

    def get_queryset(self):
        return Promotion.objects.select_related(
            "company", "state", "municipality", "city").prefetch_related("images")

    def build_detail(self, p):
        image = p.image or (p.company.logo if p.company else None)
        return {
            "kind": "Descuento", "title": p.name,
            "image_url": image.url if image else None,
            "description": p.description,
            "institution": p.company.name if p.company else None,
            "sede": None,
            "location": _location_label(p.state, p.municipality, p.city),
            "date_label": _date_label(p.start_date, p.end_date),
            "age_label": None,
            "requirements": [],
            "requirements_text": p.requirements,
            "extra_images": [i.image.url for i in p.images.all() if i.image],
            "external_url": p.access_link,
            "external_label": "Ir a la promoción",
            "back_url": reverse("youth:descuentos"),
        }


# ---------------------------------------------------------------------------
# Encuestas: listado + responder (ÚNICO endpoint de escritura)
# ---------------------------------------------------------------------------
class EncuestasListView(YouthAccessMixin, TemplateView):
    template_name = "youth/encuestas.html"
    active_nav = "encuestas"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tests = available_tests_for(self.request.user)
        answered = set(
            TestSession.objects.filter(user=self.request.user, test__in=[t.id for t in tests])
            .values_list("test_id", flat=True)
        )
        ctx["encuestas"] = [
            {
                "test": t,
                "answered": t.id in answered,
                "responder_url": reverse("youth:encuesta_responder", args=[t.pk]),
                "num_preguntas": t.questions.count(),
                "location": _location_label(t.state, t.municipality, t.city),
            }
            for t in tests
        ]
        return ctx


class TestResponderView(YouthAccessMixin, FormView):
    """Responder una encuesta. Crea `TestSession` + `Answer` (la única escritura del portal)."""

    template_name = "youth/test_responder.html"
    active_nav = "encuestas"

    def dispatch(self, request, *args, **kwargs):
        self.test = get_object_or_404(
            Test.objects.prefetch_related("questions__choices"),
            pk=kwargs["pk"], is_active=True,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        data = self.request.POST if self.request.method == "POST" else None
        return build_response_form(self.test, data)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["test"] = self.test
        ctx["available"] = self.test.is_available_for_user(self.request.user)
        return ctx

    def form_valid(self, form):
        if self.is_preview:
            messages.info(self.request, "Vista previa: las respuestas no se guardan.")
            return redirect("youth:encuestas")
        if not self.test.is_available_for_user(self.request.user):
            messages.error(self.request, "Esta encuesta no está disponible para tu perfil.")
            return redirect("youth:encuestas")

        with transaction.atomic():
            session = TestSession.objects.create(user=self.request.user, test=self.test)
            score = 0
            for q in self.test.questions.all():
                value = form.cleaned_data.get(f"q_{q.id}")
                if q.question_type == Question.MULTIPLE_CHOICE:
                    Answer.objects.create(session=session, question=q, chosen_choice=value)
                    if value and value.is_correct:
                        score += 1
                else:
                    Answer.objects.create(session=session, question=q, text_answer=value or "")
            session.score = score
            session.save(update_fields=["score"])

        messages.success(self.request, f"¡Gracias! Tu encuesta «{self.test.name}» fue registrada.")
        return redirect("youth:encuestas")

    def get_success_url(self):
        return reverse("youth:encuestas")


# ---------------------------------------------------------------------------
# Mapa interactivo
# ---------------------------------------------------------------------------
class MapaView(YouthAccessMixin, TemplateView):
    template_name = "youth/mapa.html"
    active_nav = "mapa"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["map_url"] = reverse("youth:mapa_data")
        return ctx


class MapaDataView(YouthAccessMixin, View):
    """JSON de pines (Programas + Eventos) filtrados al perfil. Consumido por youth_portal.js."""

    active_nav = "mapa"

    def _geo(self, obj, kind):
        state_name = obj.state.name if obj.state else None
        lat, lng = centroid_for(state_name)
        return {
            "id": obj.id, "kind": kind, "name": obj.name, "state": state_name,
            "municipality": obj.municipality.name if obj.municipality else None,
            "start_date": obj.start_date.isoformat() if obj.start_date else None,
            "end_date": obj.end_date.isoformat() if obj.end_date else None,
            "lat": lat, "lng": lng,
        }

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip()
        cat = request.GET.get("cat", "all")
        results = []

        if cat in ("all", "programa"):
            qs = self.age_filter_program(self.vigentes(
                Program.objects.select_related("state", "municipality")))
            if q:
                qs = qs.filter(Q(name__icontains=q) | Q(state__name__icontains=q)
                               | Q(municipality__name__icontains=q))
            qs = self.prioritize(qs).order_by("prio")
            results += [self._geo(p, "programa") for p in qs[:MAP_LIMIT]]

        if cat in ("all", "evento"):
            qs = self.vigentes(Event.objects.select_related("state", "municipality", "city"))
            if q:
                qs = qs.filter(Q(name__icontains=q) | Q(state__name__icontains=q)
                               | Q(municipality__name__icontains=q) | Q(city__name__icontains=q))
            qs = self.prioritize(qs).order_by("prio")
            results += [self._geo(e, "evento") for e in qs[:MAP_LIMIT]]

        return JsonResponse({"count": len(results), "results": results})
