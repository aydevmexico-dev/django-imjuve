"""Pruebas del Portal de Jóvenes (rol GENERAL): filtrado, acceso, envío y solo-lectura.

Se ejecutan contra SQLite (el rol Postgres local no puede crear BD de test):
    DATABASE_URL="sqlite:///t.sqlite3" .venv/bin/python manage.py test tests.test_youth_portal
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import YouthProfile
from programs.models import Event, Program
from promotions.models import Company, Promotion
from states.models import Location, Municipality, State
from tests.models import Choice, Question, Test, TestSession

User = get_user_model()


class YouthPortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.future = cls.today + timedelta(days=30)
        cls.past = cls.today - timedelta(days=5)

        cls.jal = State.objects.create(name="JALISCO")
        cls.cdmx = State.objects.create(name="DISTRITO FEDERAL")
        muni = Municipality.objects.create(state=cls.jal, name="GUADALAJARA")
        loc = Location.objects.create(
            municipality=muni, postal_code="44100", name="CENTRO", settlement_type="Colonia")

        # Joven de Jalisco, 22 años.
        cls.youth = User.objects.create_user(
            email="joven@imjuve.gob.mx", password="x", role=User.Role.GENERAL)
        YouthProfile.objects.create(
            user=cls.youth, birthdate=date(2004, 1, 1), residence_location=loc)

        cls.admin = User.objects.create_user(
            email="admin@imjuve.gob.mx", password="x", role=User.Role.SUPER)

        # --- Programas ---
        cls.prog_local = Program.objects.create(
            name="Beca local", state=cls.jal, age_from=15, age_to=29,
            end_date=cls.future, description="x")
        cls.prog_nacional = Program.objects.create(
            name="Beca nacional", state=None, end_date=cls.future, description="x")
        cls.prog_otro = Program.objects.create(
            name="Beca de otro estado", state=cls.cdmx, end_date=cls.future, description="x")
        cls.prog_vencida = Program.objects.create(
            name="Beca vencida", state=cls.jal, end_date=cls.past, description="x")
        cls.prog_edad = Program.objects.create(
            name="Beca para adultos", state=cls.jal, age_from=40, age_to=60,
            end_date=cls.future, description="x")

        Event.objects.create(name="Feria juvenil", state=cls.jal, end_date=cls.future, description="x")
        company = Company.objects.create(name="Cinepolis", state=cls.jal)
        Promotion.objects.create(name="2x1 boletos", company=company, state=cls.jal, end_date=cls.future)

        # --- Encuesta nacional, sin restricción de edad (disponible al joven) ---
        cls.test = Test.objects.create(name="Encuesta de opinión", is_active=True)
        cls.q_txt = Question.objects.create(test=cls.test, text="¿Comentarios?", question_type="TXT")
        cls.q_mc = Question.objects.create(test=cls.test, text="¿Te gustó?", question_type="MC")
        cls.c_yes = Choice.objects.create(question=cls.q_mc, text="Sí", is_correct=True)
        cls.c_no = Choice.objects.create(question=cls.q_mc, text="No", is_correct=False)

    # ------------------------------ Acceso -------------------------------
    def test_anonimo_redirige_a_login(self):
        resp = self.client.get(reverse("youth:dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp.url)

    def test_joven_entra(self):
        self.client.force_login(self.youth)
        resp = self.client.get(reverse("youth:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["is_preview"])

    def test_admin_modo_preview(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("youth:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["is_preview"])   # no se rompe pese a no tener youth_profile

    # ---------------------------- Filtrado -------------------------------
    def test_programas_filtra_y_prioriza(self):
        self.client.force_login(self.youth)
        resp = self.client.get(reverse("youth:programas"))
        titulos = [c["title"] for c in resp.context["cards"]]
        # Vigencia: la vencida fuera. Edad: la de adultos fuera.
        self.assertNotIn("Beca vencida", titulos)
        self.assertNotIn("Beca para adultos", titulos)
        # Prioritización (no exclusión): local, nacional y de otro estado, en ese orden.
        self.assertEqual(titulos, ["Beca local", "Beca nacional", "Beca de otro estado"])
        self.assertTrue(resp.context["cards"][0]["is_local"])

    def test_region_detectada_es_jalisco(self):
        self.client.force_login(self.youth)
        resp = self.client.get(reverse("youth:dashboard"))
        self.assertEqual(resp.context["region_label"], "Jalisco")   # fallback al perfil

    # --------------------- Detalle bajo demanda (AJAX) -------------------
    def test_detalle_ajax_devuelve_fragmento(self):
        self.client.force_login(self.youth)
        url = reverse("youth:programa_detalle", args=[self.prog_local.pk])
        resp = self.client.get(url, HTTP_X_REQUESTED_WITH="fetch")
        html = resp.content.decode()
        self.assertIn("ydetail", html)
        self.assertNotIn('class="sidebar"', html)   # fragmento, no página completa

    # --------------------- Encuesta: ENVÍO (único write) -----------------
    def test_responder_crea_sesion_y_respuestas(self):
        self.client.force_login(self.youth)
        url = reverse("youth:encuesta_responder", args=[self.test.pk])
        resp = self.client.post(url, {
            f"q_{self.q_txt.id}": "Todo bien",
            f"q_{self.q_mc.id}": str(self.c_yes.pk),
        })
        self.assertRedirects(resp, reverse("youth:encuestas"))
        sesion = TestSession.objects.get(user=self.youth, test=self.test)
        self.assertEqual(sesion.answers.count(), 2)
        self.assertEqual(sesion.score, 1)   # una opción correcta
        self.assertTrue(sesion.answers.filter(question=self.q_mc, chosen_choice=self.c_yes).exists())
        self.assertTrue(sesion.answers.filter(question=self.q_txt, text_answer="Todo bien").exists())

    def test_admin_preview_no_guarda(self):
        self.client.force_login(self.admin)
        url = reverse("youth:encuesta_responder", args=[self.test.pk])
        resp = self.client.post(url, {f"q_{self.q_txt.id}": "x"})
        self.assertRedirects(resp, reverse("youth:encuestas"))
        self.assertFalse(TestSession.objects.filter(user=self.admin).exists())

    # ------------------------------- Mapa --------------------------------
    def test_mapa_data_filtrado(self):
        self.client.force_login(self.youth)
        resp = self.client.get(reverse("youth:mapa_data"))
        data = resp.json()
        nombres = {r["name"] for r in data["results"]}
        self.assertIn("Beca local", nombres)
        self.assertIn("Feria juvenil", nombres)
        self.assertNotIn("Beca vencida", nombres)        # vigencia
        self.assertNotIn("Beca para adultos", nombres)   # edad
        for r in data["results"]:                        # centroide estatal presente
            self.assertIsInstance(r["lat"], (int, float))

    # --------------------------- Solo lectura ----------------------------
    def test_listados_no_aceptan_post(self):
        self.client.force_login(self.youth)
        for name in ("youth:programas", "youth:eventos", "youth:descuentos"):
            resp = self.client.post(reverse(name))
            self.assertEqual(resp.status_code, 405, name)   # ListView: solo GET
