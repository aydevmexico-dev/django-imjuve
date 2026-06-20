from django.db import models
from states.models import State, Municipality, City

class Company(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre de la Empresa")
    state = models.ForeignKey(
        State, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='companies', verbose_name="Estado",
        help_text="Estado al que pertenece la empresa. Vacío = alcance nacional.",
    )
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True, verbose_name="Logo de la Empresa")
    description = models.TextField(verbose_name="Descripción de la Empresa", blank=True, null=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"

class Promotion(models.Model):
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True, related_name='promotions', verbose_name="Estado")
    municipality = models.ForeignKey(Municipality, on_delete=models.SET_NULL, null=True, blank=True, related_name='promotions', verbose_name="Municipio")
    city = models.ForeignKey(City , on_delete=models.SET_NULL, null=True, blank=True, related_name='promotions', verbose_name="Ciudad") 
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='promotions', verbose_name="Empresa")
    name = models.CharField(max_length=100, verbose_name="Nombre de la Promoción")
    description = models.TextField(verbose_name="Descripción de la Promoción", blank=True, null=True)
    start_date = models.DateField(verbose_name="Fecha de Inicio", db_index=True, help_text="Fecha en formato AAAA-MM-DD", null=True, blank=True)
    end_date = models.DateField(verbose_name="Fecha de Fin", null=True, blank=True, help_text="Fecha en formato AAAA-MM-DD")
    requirements = models.TextField(verbose_name="Requisitos para la Promoción", blank=True, null=True)
    access_link = models.URLField(verbose_name="Enlace de Acceso a la Promoción", null=True, blank=True)
    image = models.ImageField(upload_to='promotion_images/', null=True, blank=True, verbose_name="Imagen de la Promoción")

    def __str__(self):
        return f"{self.name} ({self.company.name})"
    
    class Meta:
        verbose_name = "Promoción"
        verbose_name_plural = "Promociones"

class PromotionImage(models.Model):
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='images', verbose_name="Promoción")
    image = models.ImageField(upload_to='promotion_images/', verbose_name="Imagen de la Promoción")

    def __str__(self):
        return f"Imagen de {self.promotion.name}"
    
    class Meta:
        verbose_name = "Imagen de Promoción"
        verbose_name_plural = "Imágenes de Promociones"


