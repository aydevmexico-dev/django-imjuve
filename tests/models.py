from django.db import models
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone


class Test(models.Model):
    name = models.CharField(max_length=100)
    organizing_institution = models.CharField(max_length=200, verbose_name="Institución Organizadora", null=True, blank=True)
    date_start = models.DateField(verbose_name="Fecha de Inicio", db_index=True, null=True, blank=True)
    date_end = models.DateField(verbose_name="Fecha de Fin", null=True, blank=True)
    is_active = models.BooleanField(default=True,verbose_name="¿Activo?")  # Solo los Tests activos se muestran a los usuarios.

    # --- Segmentación por edad (opcional; vacío = sin filtro de edad) ---
    age_min = models.PositiveIntegerField("Edad mínima", null=True, blank=True)
    age_max = models.PositiveIntegerField("Edad máxima", null=True, blank=True)

    # --- Segmentación territorial (opcional; todo vacío = alcance nacional) ---
    state = models.ForeignKey(
        "states.State", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tests", verbose_name="Estado",
    )
    municipality = models.ForeignKey(
        "states.Municipality", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tests", verbose_name="Municipio",
    )
    city = models.ForeignKey(
        "states.City", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tests", verbose_name="Ciudad",
    )

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        # El rango de edad debe ser coherente.
        if self.age_min is not None and self.age_max is not None and self.age_min > self.age_max:
            raise ValidationError({"age_max": "La edad máxima no puede ser menor que la edad mínima."})
        # Municipio/Ciudad deben pertenecer al Estado elegido (si ambos están definidos).
        if self.state_id and self.municipality_id and self.municipality.state_id != self.state_id:
            raise ValidationError({"municipality": "El municipio no pertenece al estado seleccionado."})
        if self.state_id and self.city_id and self.city.state_id != self.state_id:
            raise ValidationError({"city": "La ciudad no pertenece al estado seleccionado."})

    @staticmethod
    def _calculate_age(birthdate) -> int:
        # Edad dinámica: año actual menos año de nacimiento, restando 1 si aún no cumple este año.
        today = timezone.now().date()
        return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))

    def is_available_for_user(self, user) -> bool:
        """¿`user` (CustomUser) puede responder este test? Valida vigencia, edad y territorio."""
        # 1) Debe estar activo y vigente por fechas (si se definieron).
        if not self.is_active:
            return False
        today = timezone.now().date()
        if self.date_start and today < self.date_start:
            return False
        if self.date_end and today > self.date_end:
            return False

        # El reverse OneToOne lanza RelatedObjectDoesNotExist si no hay perfil
        # (NO devuelve None con getattr), por eso lo envolvemos en try/except.
        try:
            profile = user.youth_profile
        except ObjectDoesNotExist:
            profile = None

        # 2) Filtro por edad (opcional). Si el test exige edad y no hay birthdate, no es elegible.
        if self.age_min is not None or self.age_max is not None:
            if not profile or not profile.birthdate:
                return False
            age = self._calculate_age(profile.birthdate)
            if self.age_min is not None and age < self.age_min:
                return False
            if self.age_max is not None and age > self.age_max:
                return False

        # 3) Filtro territorial: gana el nivel más específico definido en el test.
        if self.city_id or self.municipality_id or self.state_id:
            # Necesitamos la ubicación de residencia del joven.
            if not profile or not profile.residence_location_id:
                return False
            loc = profile.residence_location  # states.Location
            if self.city_id:
                return loc.city_id == self.city_id
            if self.municipality_id:
                return loc.municipality_id == self.municipality_id
            # Ruta a Estado: Location -> Municipality -> State (Location no tiene FK directa a State).
            return loc.municipality.state_id == self.state_id

        # 4) Sin restricción territorial => alcance nacional.
        return True
    class Meta:
        verbose_name = "Test/Cuestionario"
        verbose_name_plural = "Tests/Cuestionarios"

def available_tests_for(user):
    """Lista de Tests que `user` puede responder.

    Para un usuario × muchos tests no hay N+1: `user.youth_profile`,
    `.residence_location` y `.municipality` se cachean en la instancia tras el
    primer acceso. El `select_related` precarga la geografía del test para mostrarla.
    """
    tests = Test.objects.filter(is_active=True).select_related("state", "municipality", "city")
    return [t for t in tests if t.is_available_for_user(user)]


class Question(models.Model):
    TEXT = 'TXT'
    MULTIPLE_CHOICE = 'MC'
    QUESTION_TYPES = [(TEXT, 'Texto Libre'), (MULTIPLE_CHOICE, 'Opción Múltiple')]

    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField(verbose_name="Texto de la pregunta")
    question_type = models.CharField(max_length=3, choices=QUESTION_TYPES, default=TEXT, verbose_name="Tipo de pregunta")

    def __str__(self):
        return f"{self.test.name} - {self.text[:30]}"
    class Meta:
        verbose_name = "Pregunta"
        verbose_name_plural = "Preguntas"


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255, verbose_name="Texto de la opción")
    is_correct = models.BooleanField(default=False, verbose_name="¿Correcta?")

    def __str__(self):
        return self.text
    
    class Meta:
        verbose_name = "Opción de Pregunta"
        verbose_name_plural = "Opciones de Preguntas"


class TestSession(models.Model):
    # Apuntamos al nuevo modelo CustomUser usando settings.AUTH_USER_MODEL
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='test_sessions')
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='sessions')
    completed_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de resolución")
    score = models.FloatField(default=0.0, verbose_name="Puntuación/Nota")

    class Meta:
        verbose_name = "Sesión de Test"
        verbose_name_plural = "Sesiones de Tests"
        ordering = ['-completed_at']

    def __str__(self):
        return f"{self.user.email} - {self.test.name} ({self.completed_at.strftime('%Y-%m-%d %H:%M')})"


class Answer(models.Model):
    session = models.ForeignKey(TestSession, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    text_answer = models.TextField(null=True, blank=True)
    chosen_choice = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Respuesta de {self.session.user.email} a la pregunta {self.question.id}"
    
    class Meta:
        verbose_name = "Respuesta"
        verbose_name_plural = "Respuestas"