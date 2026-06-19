from django.db import models

class State(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Estado")
    abbreviation = models.CharField(max_length=10, null=True, blank=True, verbose_name="Abreviación")

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
            if self.name:
                self.name = self.name.strip().upper()
            if not self.abbreviation:
                self.abbreviation = self.name[:4].upper()
            else:
                self.abbreviation = self.abbreviation.strip().upper()
            super(State, self).save(*args, **kwargs)

    class Meta:
        verbose_name = "Estado"
        verbose_name_plural = "Estados"


class Municipality(models.Model):
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='municipalities', verbose_name="Estado")
    name = models.CharField(max_length=150, verbose_name="Municipio")
    
    def __str__(self):
        return f"{self.name}, {self.state.name}"
        
    class Meta:
        verbose_name = "Municipio"
        verbose_name_plural = "Municipios"
        unique_together = ('state', 'name')
    
    
class City(models.Model):
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='cities', verbose_name="Estado")
    name = models.CharField(max_length=150, verbose_name="Ciudad")
   
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Ciudad"
        verbose_name_plural = "Ciudades"
        unique_together = ('state', 'name')


class Location(models.Model):
    municipality = models.ForeignKey(Municipality, on_delete=models.CASCADE, related_name='locations', verbose_name="Municipio")
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name='locations', verbose_name="Ciudad")    
    postal_code = models.CharField(max_length=10, db_index=True, verbose_name="Código Postal")
    name = models.CharField(max_length=150, verbose_name="Asentamiento")    
    settlement_type = models.CharField(max_length=100, verbose_name="Tipo de Asentamiento")

    def __str__(self):
        return f"{self.postal_code} - {self.name} ({self.settlement_type})"
    
    class Meta:
        verbose_name = "Asentamiento" # O "Ubicación"
        verbose_name_plural = "Asentamientos"