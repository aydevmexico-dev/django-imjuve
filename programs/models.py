from django.db import models
from states.models import State, Municipality, City

class Program(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Programa")
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True, related_name='programs', verbose_name="Estado")
    start_date = models.DateField(verbose_name="Fecha de Inicio", db_index=True, help_text="Fecha en formato AAAA-MM-DD", null=True, blank=True)
    municipality = models.ForeignKey(Municipality, on_delete=models.SET_NULL, null=True, blank=True, related_name='programs', verbose_name="Municipio")
    cities = models.ManyToManyField(City, blank=True, related_name='programs', verbose_name="Ciudades")
    age_from = models.PositiveIntegerField(verbose_name="Edad Mínima", null=True, blank=True)
    age_to = models.PositiveIntegerField(verbose_name="Edad Máxima", null=True, blank=True)
    end_date = models.DateField(verbose_name="Fecha de Fin", null=True, blank=True, help_text="Fecha en formato AAAA-MM-DD")
    organizing_institution = models.CharField(max_length=200, verbose_name="Institución Organizadora", null=True, blank=True)
    access_link = models.URLField(verbose_name="Enlace de Acceso al Programa", null=True, blank=True)
    image = models.ImageField(upload_to='program_images/', null=True, blank=True, verbose_name="Poster del Programa")
    description = models.TextField(verbose_name="Descripción del Programa")

    def __str__(self):
        return f"{self.name} ({self.state.name if self.state else 'Sin Estado'})"

    class Meta:
        verbose_name = "Programa"
        verbose_name_plural = "Programas"

class Event(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nombre del Evento")
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True, related_name='events', verbose_name="Estado")
    municipality = models.ForeignKey(Municipality, on_delete=models.SET_NULL, null=True,blank=True, related_name='events', verbose_name="Municipio")
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name='events', verbose_name="Ciudad")
    start_date = models.DateField(verbose_name="Fecha de Inicio", db_index=True, help_text="Fecha en formato AAAA-MM-DD", null=True, blank=True)
    end_date = models.DateField(verbose_name="Fecha de Fin", null=True, blank=True, help_text="Fecha en formato AAAA-MM-DD")
    headquarters = models.CharField(max_length=200, verbose_name="Sede del Evento", null=True, blank=True)
    organizing_institution = models.CharField(max_length=200, verbose_name="Institución Organizadora", null=True, blank=True)
    image = models.ImageField(upload_to='program_images/', null=True, blank=True, verbose_name="Poster del Evento")
    description = models.TextField(verbose_name="Descripción del Evento")

    def __str__(self):
        return f"{self.name} ({self.state.name if self.state else 'Sin Estado'})"
    
    class Meta:
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"

class Requirements(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='requirements', verbose_name="Programa", null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='requirements', verbose_name="Evento", null=True, blank=True)
    name = models.CharField(max_length=200, verbose_name="Requisito")

    def __str__(self):
        return f"{self.name} ({self.program.name if self.program else 'Sin Programa'})"
    
    class Meta:
        verbose_name = "Requisito"
        verbose_name_plural = "Requisitos"

class Images (models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='images', verbose_name="Programa", null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='images', verbose_name="Evento", null=True, blank=True)
    image = models.ImageField(upload_to='images_images/', null=True, blank=True, verbose_name="Imagen de Documentación")

    def __str__(self):
        return f"Imagen para {self.program.name if self.program else 'Sin Programa'} - {self.event.name if self.event else 'Sin Evento'}"
    
    class Meta:
        verbose_name = "Imagen"
        verbose_name_plural = "Imágenes"

