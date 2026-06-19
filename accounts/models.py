from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models


class CustomUserManager(BaseUserManager):
    """Manager para un modelo de usuario que se autentica con correo en lugar de username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("El correo electrónico es obligatorio")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", CustomUser.Role.GENERAL)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        extra_fields.setdefault("role", CustomUser.Role.SUPER)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    """Usuario que inicia sesión con correo electrónico y se diferencia por rol."""

    class Role(models.TextChoices):
        SUPER = "SUPER", "Super Administrador"
        ESTATAL = "ESTATAL", "Administrador Estatal"
        GENERAL = "GENERAL", "Usuario General"

    # Eliminamos username: la autenticación es por correo.
    username = None
    email = models.EmailField("Correo electrónico", unique=True)

    role = models.CharField(
        "Rol", max_length=10, choices=Role.choices, default=Role.GENERAL
    )
    assigned_state = models.ForeignKey(
        "states.State",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admins",
        verbose_name="Estado asignado",
        help_text="Solo aplica para Administradores Estatales.",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # email y password se piden automáticamente

    objects = CustomUserManager()

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["assigned_state"]),
        ]

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        # Invariante de negocio: solo el Estatal tiene (y requiere) un estado asignado.
        if self.role == self.Role.ESTATAL and self.assigned_state_id is None:
            raise ValidationError(
                {"assigned_state": "Un Administrador Estatal requiere un Estado asignado."}
            )
        if self.role != self.Role.ESTATAL and self.assigned_state_id is not None:
            raise ValidationError(
                {"assigned_state": "Solo los Administradores Estatales pueden tener Estado asignado."}
            )

    def save(self, *args, **kwargs):
        # Mantenemos los flags nativos de Django consistentes con el rol de negocio.
        if self.role == self.Role.SUPER:
            self.is_superuser = True
            self.is_staff = True
        elif self.role == self.Role.ESTATAL:
            self.is_superuser = False
            self.is_staff = True
        else:  # GENERAL
            self.is_superuser = False
            self.is_staff = False
        super().save(*args, **kwargs)


class YouthProfile(models.Model):
    """Datos específicos del Usuario General (joven/estudiante) para el futuro frontend."""

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="youth_profile",
        verbose_name="Usuario",
    )
    birthdate = models.DateField("Fecha de nacimiento", null=True, blank=True)
    phone = models.CharField("Teléfono", max_length=20, null=True, blank=True)
    curp = models.CharField("CURP", max_length=18, unique=True, null=True, blank=True)
    school = models.CharField("Escuela", max_length=200, null=True, blank=True)
    occupation = models.CharField("Ocupación", max_length=200, null=True, blank=True)
    residence_postal_code = models.CharField(
        "Código Postal", max_length=10, null=True, blank=True
    )
    residence_location = models.ForeignKey(
        "states.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="residents",
        verbose_name="Asentamiento de residencia",
    )

    class Meta:
        verbose_name = "Perfil de Joven"
        verbose_name_plural = "Perfiles de Jóvenes"

    def __str__(self):
        return f"Perfil de {self.user.email}"
