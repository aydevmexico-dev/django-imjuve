"""Pruebas del Expediente Digital (app `records`).

Cubre: autocreación por signal, acceso propio (sin IDOR), endpoints AJAX de bitácora
(favoritos + búsquedas) con regla fail-safe por rol, restricciones de integridad del modelo,
CSRF en escritura y aislamiento territorial del visor de administradores.

Se ejecutan contra SQLite (el rol Postgres local no puede crear BD de test):
    DATABASE_URL="sqlite:///t.sqlite3" .venv/bin/python manage.py test tests.test_records
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import YouthProfile
from programs.models import Event, Program
from states.models import Location, Municipality, State
from tests.models import Test, TestSession

from records.models import DigitalRecord, RecentSearch, SavedItem

User = get_user_model()


class RecordsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.future = timezone.localdate() + timedelta(days=30)

        cls.jal = State.objects.create(name="JALISCO")
        cls.cdmx = State.objects.create(name="DISTRITO FEDERAL")
        muni_jal = Municipality.objects.create(state=cls.jal, name="GUADALAJARA")
        muni_cdmx = Municipality.objects.create(state=cls.cdmx, name="CUAUHTEMOC")
        loc_jal = Location.objects.create(
            municipality=muni_jal, postal_code="44100", name="CENTRO", settlement_type="Colonia")
        loc_cdmx = Location.objects.create(
            municipality=muni_cdmx, postal_code="06000", name="CENTRO", settlement_type="Colonia")

        # Jóvenes (rol GENERAL) — el signal debe crearles expediente automáticamente.
        cls.youth_jal = User.objects.create_user(
            email="jal@imjuve.gob.mx", password="x", role=User.Role.GENERAL)
        YouthProfile.objects.create(
            user=cls.youth_jal, birthdate=date(2004, 1, 1), residence_location=loc_jal)
        cls.youth_cdmx = User.objects.create_user(
            email="cdmx@imjuve.gob.mx", password="x", role=User.Role.GENERAL)
        YouthProfile.objects.create(
            user=cls.youth_cdmx, birthdate=date(2004, 1, 1), residence_location=loc_cdmx)

        # Administradores.
        cls.super_admin = User.objects.create_user(
            email="super@imjuve.gob.mx", password="x", role=User.Role.SUPER)
        cls.estatal_jal = User.objects.create_user(
            email="estatal@imjuve.gob.mx", password="x",
            role=User.Role.ESTATAL, assigned_state=cls.jal)

        cls.prog = Program.objects.create(
            name="Beca local", state=cls.jal, end_date=cls.future, description="x")
        cls.event = Event.objects.create(
            name="Feria juvenil", state=cls.jal, end_date=cls.future, description="x")
        cls.test = Test.objects.create(name="Encuesta", is_active=True)

    # ------------------------------------------------------------------ signal
    def test_signal_creates_record_for_general(self):
        u = User.objects.create_user(email="nuevo@imjuve.gob.mx", password="x",
                                     role=User.Role.GENERAL)
        self.assertTrue(DigitalRecord.objects.filter(user=u).exists())

    def test_signal_skips_admins(self):
        self.assertFalse(DigitalRecord.objects.filter(user=self.super_admin).exists())
        self.assertFalse(DigitalRecord.objects.filter(user=self.estatal_jal).exists())

    # ------------------------------------------------------- expediente propio
    def test_general_sees_own_record(self):
        self.client.force_login(self.youth_jal)
        resp = self.client.get(reverse("youth:expediente"))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context["record"])
        self.assertEqual(resp.context["record"].user, self.youth_jal)

    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(reverse("youth:expediente"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp["Location"].lower())

    # ----------------------------------------------------------- favoritos AJAX
    def test_toggle_favorite_add_then_remove(self):
        self.client.force_login(self.youth_jal)
        url = reverse("youth:toggle_favorito")

        r1 = self.client.post(url, {"kind": "programa", "id": self.prog.pk})
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()["saved"])
        self.assertTrue(
            SavedItem.objects.filter(record__user=self.youth_jal, program=self.prog).exists())

        r2 = self.client.post(url, {"kind": "programa", "id": self.prog.pk})
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r2.json()["saved"])
        self.assertFalse(
            SavedItem.objects.filter(record__user=self.youth_jal, program=self.prog).exists())

    def test_toggle_favorite_invalid_kind(self):
        self.client.force_login(self.youth_jal)
        resp = self.client.post(reverse("youth:toggle_favorito"),
                                {"kind": "hacker", "id": self.prog.pk})
        self.assertEqual(resp.status_code, 400)

    def test_toggle_favorite_forbidden_for_admin(self):
        self.client.force_login(self.super_admin)
        resp = self.client.post(reverse("youth:toggle_favorito"),
                                {"kind": "programa", "id": self.prog.pk})
        self.assertEqual(resp.status_code, 403)

    def test_toggle_favorite_get_not_allowed(self):
        self.client.force_login(self.youth_jal)
        resp = self.client.get(reverse("youth:toggle_favorito"))
        self.assertEqual(resp.status_code, 405)

    def test_toggle_favorite_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.youth_jal)
        resp = csrf_client.post(reverse("youth:toggle_favorito"),
                                {"kind": "programa", "id": self.prog.pk})
        self.assertEqual(resp.status_code, 403)

    # ------------------------------------------------------------ búsquedas AJAX
    def test_log_search_creates_entry(self):
        self.client.force_login(self.youth_jal)
        resp = self.client.post(reverse("youth:log_busqueda"), {"q": "becas 2026"})
        self.assertEqual(resp.status_code, 204)
        self.assertTrue(
            RecentSearch.objects.filter(record__user=self.youth_jal, query="becas 2026").exists())

    def test_log_search_rejects_empty(self):
        self.client.force_login(self.youth_jal)
        resp = self.client.post(reverse("youth:log_busqueda"), {"q": "   "})
        self.assertEqual(resp.status_code, 400)

    def test_log_search_forbidden_for_admin(self):
        self.client.force_login(self.estatal_jal)
        resp = self.client.post(reverse("youth:log_busqueda"), {"q": "algo"})
        self.assertEqual(resp.status_code, 403)

    # ------------------------------------------- restricciones de integridad
    def test_saveditem_rejects_two_targets(self):
        record = DigitalRecord.objects.get(user=self.youth_jal)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SavedItem.objects.create(record=record, program=self.prog, event=self.event)

    def test_saveditem_rejects_zero_targets(self):
        record = DigitalRecord.objects.get(user=self.youth_jal)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SavedItem.objects.create(record=record)

    def test_saveditem_unique_per_program(self):
        record = DigitalRecord.objects.get(user=self.youth_jal)
        SavedItem.objects.create(record=record, program=self.prog)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SavedItem.objects.create(record=record, program=self.prog)

    # ----------------------------------- visor admin: aislamiento territorial
    def test_super_sees_any_record(self):
        self.client.force_login(self.super_admin)
        url = reverse("panel:joven_expediente", args=[self.youth_cdmx.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_estatal_sees_record_in_own_state(self):
        self.client.force_login(self.estatal_jal)
        url = reverse("panel:joven_expediente", args=[self.youth_jal.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_estatal_blocked_from_other_state_record(self):
        # IDOR: alterar el pk hacia un joven de otro estado no debe revelar el recurso.
        self.client.force_login(self.estatal_jal)
        url = reverse("panel:joven_expediente", args=[self.youth_cdmx.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_general_blocked_from_admin_record_view(self):
        self.client.force_login(self.youth_jal)
        url = reverse("panel:joven_expediente", args=[self.youth_cdmx.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
