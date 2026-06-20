"""Formulario de alta/edición de Encuestas/Tests con scope territorial.

`Test.state` es nullable (un test sin estado = alcance nacional): el SUPER puede dejarlo
vacío; al ESTATAL se le ancla a su estado. `Test.clean()` (en el modelo) revalida la
coherencia municipio/ciudad∈estado y el rango de edad, además del `clean()` del form base.
"""

from django import forms
from django.forms import inlineformset_factory

from core.forms import GeoScopedModelForm

from .models import Choice, Question, Test


class TestForm(GeoScopedModelForm):
    class Meta:
        model = Test
        fields = [
            "name", "organizing_institution", "is_active",
            "date_start", "date_end", "age_min", "age_max",
            "state", "municipality", "city",
        ]
        widgets = {
            "date_start": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "date_end": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }


# ============================================================================
# Reactivos de la encuesta: Preguntas (Question) y, en cascada, sus Opciones (Choice)
# ============================================================================
# Estas clases alimentan el flujo unificado de alta/edición de encuestas: el
# `Test` se guarda junto con sus preguntas (formset externo) y cada pregunta de
# Opción Múltiple guarda sus opciones (formset interno anidado). Las clases CSS
# institucionales (`form-textarea`, `form-select`, `form-input`) se estampan aquí
# en los widgets para no escribir estilos inline en las plantillas.


class QuestionForm(forms.ModelForm):
    """Una pregunta del cuestionario. El tipo decide si se piden opciones (MC)."""

    class Meta:
        model = Question
        fields = ["text", "question_type"]
        widgets = {
            "text": forms.Textarea(attrs={
                "class": "form-textarea", "rows": 2,
                "placeholder": "Redacta la pregunta…",
            }),
            "question_type": forms.Select(attrs={
                "class": "form-select", "data-qtype": "1",
            }),
        }


class ChoiceForm(forms.ModelForm):
    """Una opción válida de una pregunta de Opción Múltiple."""

    class Meta:
        model = Choice
        fields = ["text", "is_correct"]
        widgets = {
            "text": forms.TextInput(attrs={
                "class": "form-input", "placeholder": "Texto de la opción…",
            }),
        }


# Formset externo: las Preguntas que cuelgan de un Test.
QuestionFormSet = inlineformset_factory(
    Test, Question, form=QuestionForm,
    fk_name="test", extra=1, can_delete=True,
)

# Formset interno (anidado): las Opciones que cuelgan de cada Pregunta.
ChoiceFormSet = inlineformset_factory(
    Question, Choice, form=ChoiceForm,
    fk_name="question", extra=2, can_delete=True,
)
