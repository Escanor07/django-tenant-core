# tenant_core/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from .context import get_current_tenant
from .exceptions import SubscriptionExpired, SubscriptionSuspended, PlanLimitExceeded


# ─── Planes disponibles ───────────────────────────────────────────────────────

class Plan(models.Model):
    """
    Define los planes disponibles y sus límites.
    Se almacena en DB para poder modificarlos sin tocar código.
    """
    PLAN_CHOICES = [
        ('free',       'Free'),
        ('pro',        'Pro'),
        ('enterprise', 'Enterprise'),
    ]

    nombre      = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True)
    descripcion = models.TextField(blank=True)
    precio      = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Límites — None significa ilimitado
    max_usuarios  = models.PositiveIntegerField(null=True, blank=True, help_text="None = ilimitado")
    max_registros = models.PositiveIntegerField(null=True, blank=True, help_text="Límite genérico de registros principales. None = ilimitado")

    # Límites extra en JSON para que cada proyecto agregue los suyos sin migrar
    # ej: {"max_vehiculos": 10, "max_conductores": 5}
    limites_extra = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        verbose_name = 'Plan'
        verbose_name_plural = 'Planes'

    def __str__(self):
        return self.get_nombre_display()

    def get_limite(self, key):
        """Obtiene un límite por nombre. Retorna None si es ilimitado."""
        return self.limites_extra.get(key)


# ─── Suscripción ──────────────────────────────────────────────────────────────

class Subscription(models.Model):
    """
    Controla la vigencia y estado de pago del tenant.
    Un tenant siempre tiene una suscripción activa (la más reciente).
    El historial se conserva para auditoría.
    """
    ESTADO_CHOICES = [
        ('activa',    'Activa'),
        ('vencida',   'Vencida'),
        ('suspendida','Suspendida'),
        ('cancelada', 'Cancelada'),
    ]

    # tenant se define como FK en el proyecto (ver abajo en Tenant base)
    fecha_inicio    = models.DateField()
    fecha_fin       = models.DateField()
    estado          = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activa')
    renovacion_auto = models.BooleanField(default=True)
    notas           = models.TextField(blank=True)  # para notas internas del admin
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-fecha_inicio']
        verbose_name = 'Suscripción'
        verbose_name_plural = 'Suscripciones'

    def __str__(self):
        return f"Suscripción {self.estado} — vence {self.fecha_fin}"

    @property
    def dias_restantes(self):
        delta = self.fecha_fin - timezone.now().date()
        return max(delta.days, 0)

    @property
    def esta_vigente(self):
        return (
            self.estado == 'activa'
            and self.fecha_fin >= timezone.now().date()
        )

    def verificar_acceso(self):
        """
        Lanza excepción si la suscripción no permite acceso.
        Se llama desde el middleware.
        """
        if self.estado == 'suspendida':
            raise SubscriptionSuspended(
                "Tu cuenta está suspendida. Contacta a soporte."
            )
        if self.estado == 'cancelada':
            raise SubscriptionSuspended(
                "Tu suscripción ha sido cancelada."
            )
        if not self.esta_vigente:
            raise SubscriptionExpired(
                f"Tu suscripción venció el {self.fecha_fin}. Renuévala para continuar."
            )


# ─── Tenant Base ──────────────────────────────────────────────────────────────

class Tenant(models.Model):
    """
    Modelo base abstracto. Cada proyecto lo extiende con sus propios campos.
    """
    name       = models.CharField(max_length=200)
    slug       = models.SlugField(unique=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    def get_suscripcion_activa(self):
        """Retorna la suscripción más reciente."""
        return self.suscripciones.filter(estado='activa').first()

    def verificar_suscripcion(self):
        """Verifica que la suscripción permita acceso. Lanza excepción si no."""
        suscripcion = self.get_suscripcion_activa()
        if not suscripcion:
            raise SubscriptionExpired("No tienes una suscripción activa.")
        suscripcion.verificar_acceso()

    def verificar_limite(self, key, queryset):
        """
        Verifica si se puede agregar un registro más según el plan.
        
        Uso:
            tenant.verificar_limite('max_vehiculos', tenant.vehiculo_set.all())
        """
        suscripcion = self.get_suscripcion_activa()
        if not suscripcion:
            raise SubscriptionExpired("No tienes una suscripción activa.")

        limite = suscripcion.plan.get_limite(key)
        if limite is None:
            return  # ilimitado, sin restricción

        actual = queryset.count()
        if actual >= limite:
            raise PlanLimitExceeded(
                f"Alcanzaste el límite de {limite} para '{key}' en tu plan actual.",
                limit_key=key
            )


# ─── Membresía Usuario-Tenant ─────────────────────────────────────────────────

class TenantMembership(models.Model):
    """
    Relaciona usuarios con tenants.
    - Usuarios normales: pertenecen a exactamente un tenant.
    - Admins globales: no tienen membership, tienen acceso a todo vía is_staff.
    """
    ROL_CHOICES = [
        ('owner',   'Propietario'),   # puede todo, incluyendo cancelar cuenta
        ('admin',   'Administrador'), # puede todo excepto cancelar
        ('staff',   'Staff'),         # acceso operativo
        ('readonly','Solo lectura'),
    ]

    # user y tenant se definen con FKs concretas en el proyecto
    rol        = models.CharField(max_length=20, choices=ROL_CHOICES, default='staff')
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        verbose_name = 'Membresía'
        verbose_name_plural = 'Membresías'

    def __str__(self):
        return f"{self.user} → {self.tenant} ({self.rol})"


# ─── TenantAwareModel ─────────────────────────────────────────────────────────

class TenantManager(models.Manager):
    def get_queryset(self):
        tenant = get_current_tenant()
        qs = super().get_queryset()
        return qs.filter(tenant=tenant) if tenant else qs


class TenantAwareModel(models.Model):
    """
    Modelo base para todos los modelos de negocio.
    Hereda tenant FK + filtrado automático.
    """
    # tenant se define como FK concreta en cada proyecto apuntando a su modelo Tenant
    objects     = TenantManager()  # filtrado por tenant activo
    all_objects = models.Manager() # sin filtro — solo para admin global y tareas

    def save(self, *args, **kwargs):
        if not self.tenant_id:
            tenant = get_current_tenant()
            if tenant:
                self.tenant = tenant
        super().save(*args, **kwargs)

    class Meta:
        abstract = True
