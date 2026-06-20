"""Pruebas del flujo unificado de Encuestas del panel (Test + Preguntas + Opciones).

Cubren el alta y la edición anidada vía POST con el test client, validando que el
formset externo de preguntas y el interno de opciones persistan correctamente.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tests.models import Choice, Question, Test

User = get_user_model()


def _management(prefix, total, initial=0):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }


class SurveyPanelFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.super = User.objects.create_user(
            email="super@imjuve.gob.mx", password="x", role=User.Role.SUPER
        )

    def setUp(self):
        self.client.force_login(self.super)

    def test_create_survey_with_mixed_questions(self):
        """Crea un Test con una pregunta MC (2 opciones) y una de Texto Libre."""
        data = {
            "name": "Encuesta de bienestar",
            "is_active": "on",
            "state": "", "municipality": "", "city": "",
            "age_min": "", "age_max": "", "organizing_institution": "",
            "date_start": "", "date_end": "",
        }
        data.update(_management("questions", total=2))
        # Pregunta 0 · Opción Múltiple con 2 opciones
        data.update({
            "questions-0-id": "",
            "questions-0-text": "¿Cómo calificas el servicio?",
            "questions-0-question_type": "MC",
        })
        data.update(_management("choices-0", total=2))
        data.update({
            "choices-0-0-id": "", "choices-0-0-text": "Bueno", "choices-0-0-is_correct": "on",
            "choices-0-1-id": "", "choices-0-1-text": "Malo",
        })
        # Pregunta 1 · Texto Libre (sus opciones se ignoran)
        data.update({
            "questions-1-id": "",
            "questions-1-text": "Comentarios adicionales",
            "questions-1-question_type": "TXT",
        })
        data.update(_management("choices-1", total=0))

        resp = self.client.post(reverse("panel:encuesta_crear"), data)
        self.assertRedirects(resp, reverse("panel:encuestas"))

        test = Test.objects.get(name="Encuesta de bienestar")
        self.assertEqual(test.questions.count(), 2)
        mc = test.questions.get(question_type="MC")
        self.assertEqual(mc.choices.count(), 2)
        self.assertEqual(mc.choices.filter(is_correct=True).count(), 1)
        txt = test.questions.get(question_type="TXT")
        self.assertEqual(txt.choices.count(), 0)

    def test_edit_adds_and_deletes(self):
        """Edita un Test: borra una opción, agrega una pregunta nueva."""
        test = Test.objects.create(name="Edítame")
        q = Question.objects.create(test=test, text="P1", question_type="MC")
        c1 = Choice.objects.create(question=q, text="A")
        c2 = Choice.objects.create(question=q, text="B")

        data = {
            "name": "Edítame", "is_active": "on",
            "state": "", "municipality": "", "city": "",
            "age_min": "", "age_max": "", "organizing_institution": "",
            "date_start": "", "date_end": "",
        }
        data.update(_management("questions", total=2, initial=1))
        # Pregunta existente: conserva opción A, BORRA opción B
        data.update({
            "questions-0-id": str(q.pk),
            "questions-0-text": "P1",
            "questions-0-question_type": "MC",
        })
        data.update(_management("choices-0", total=2, initial=2))
        data.update({
            "choices-0-0-id": str(c1.pk), "choices-0-0-text": "A",
            "choices-0-1-id": str(c2.pk), "choices-0-1-text": "B", "choices-0-1-DELETE": "on",
        })
        # Pregunta nueva de Texto Libre
        data.update({
            "questions-1-id": "",
            "questions-1-text": "Nueva pregunta",
            "questions-1-question_type": "TXT",
        })
        data.update(_management("choices-1", total=0))

        resp = self.client.post(reverse("panel:encuesta_editar", args=[test.pk]), data)
        self.assertRedirects(resp, reverse("panel:encuestas"))

        self.assertEqual(test.questions.count(), 2)
        self.assertFalse(Choice.objects.filter(pk=c2.pk).exists())   # B borrada
        self.assertTrue(Choice.objects.filter(pk=c1.pk).exists())    # A conservada
        self.assertTrue(test.questions.filter(text="Nueva pregunta").exists())

    def test_switch_mc_to_txt_drops_choices(self):
        """Cambiar una pregunta de MC a TXT elimina sus opciones colgantes."""
        test = Test.objects.create(name="Cambio de tipo")
        q = Question.objects.create(test=test, text="P", question_type="MC")
        Choice.objects.create(question=q, text="A")
        Choice.objects.create(question=q, text="B")

        data = {
            "name": "Cambio de tipo", "is_active": "on",
            "state": "", "municipality": "", "city": "",
            "age_min": "", "age_max": "", "organizing_institution": "",
            "date_start": "", "date_end": "",
        }
        data.update(_management("questions", total=1, initial=1))
        data.update({
            "questions-0-id": str(q.pk),
            "questions-0-text": "P",
            "questions-0-question_type": "TXT",   # MC -> TXT
        })
        data.update(_management("choices-0", total=0, initial=2))

        resp = self.client.post(reverse("panel:encuesta_editar", args=[test.pk]), data)
        self.assertRedirects(resp, reverse("panel:encuestas"))
        q.refresh_from_db()
        self.assertEqual(q.question_type, "TXT")
        self.assertEqual(q.choices.count(), 0)
