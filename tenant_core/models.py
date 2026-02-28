# tenant_core/models.py
from django.db import models
from django.utils import timezone
from .context import get_current_tenant
from .exceptions import SubscriptionExpired, SubscriptionSuspended, PlanLimitExceeded


# ─── Plan ─────────────────────────────────────────────────────────────────────


class Plan(models.Model):
    """
    Define los planes disponibles y sus límites.
    Se almacena en DB para modificarlos sin tocar código.

    Cada proyecto define sus propios PLAN_CHOICES sobreescribiendo el campo 'name'.

    Ejemplo en el proyecto:
        class MyPlan(Plan):
            PLAN_CHOICES = [('free', 'Free'), ('pro', 'Pro')]
            name = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True)

    Los límites específicos del proyecto van en extra_limits (JSONField):
        {"max_vehicles": 10, "max_drivers": 5}
    """

    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_users = models.PositiveIntegerField(
        null=True, blank=True, help_text="None = unlimited"
    )
    max_records = models.PositiveIntegerField(
        null=True, blank=True, help_text="None = unlimited"
    )
    extra_limits = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        verbose_name = "Plan"
        verbose_name_plural = "Plans"

    def __str__(self):
        return self.name

    def get_limit(self, key):
        """Retorna el límite por clave. None = ilimitado."""
        return self.extra_limits.get(key)


# ─── Subscription ─────────────────────────────────────────────────────────────


class Subscription(models.Model):
    """
    Controla la vigencia y estado de pago del tenant.
    Se conserva historial — la activa es la más reciente con status='active'.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("suspended", "Suspended"),
        ("cancelled", "Cancelled"),
    ]

    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    auto_renewal = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-start_date"]
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"

    def __str__(self):
        return f"Subscription {self.status} — expires {self.end_date}"

    @property
    def days_remaining(self):
        """Días restantes de la suscripción. Retorna 0 si ya venció."""
        delta = self.end_date - timezone.now().date()
        return max(delta.days, 0)

    @property
    def is_active(self):
        """True si la suscripción está activa y dentro de su vigencia."""
        return self.status == "active" and self.end_date >= timezone.now().date()

    def verify_access(self):
        """
        Verifica que la suscripción permita acceso.
        Lanza excepción si no — el middleware la captura.
        """
        if self.status == "suspended":
            raise SubscriptionSuspended(
                "Your account is suspended. Please contact support."
            )
        if self.status == "cancelled":
            raise SubscriptionSuspended("Your subscription has been cancelled.")
        if not self.is_active:
            raise SubscriptionExpired(
                f"Your subscription expired on {self.end_date}. Please renew to continue."
            )


# ─── Tenant ───────────────────────────────────────────────────────────────────


class Tenant(models.Model):
    """
    Modelo base abstracto del cliente B2B.
    Cada proyecto lo extiende con sus propios campos de negocio.
    """

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    def get_active_subscription(self):
        """Retorna la suscripción activa más reciente del tenant."""
        return self.subscriptions.filter(status="active").first()

    def verify_subscription(self):
        """
        Verifica que la suscripción permita acceso.
        Lanza excepción si no hay suscripción activa o está vencida.
        """
        subscription = self.get_active_subscription()
        if not subscription:
            raise SubscriptionExpired("No active subscription found.")
        subscription.verify_access()

    def verify_limit(self, key, queryset):
        """
        Verifica si se puede agregar un registro más según el plan actual.

        Uso:
            tenant.verify_limit('max_vehicles', tenant.vehicle_set.all())
        """
        subscription = self.get_active_subscription()
        if not subscription:
            raise SubscriptionExpired("No active subscription found.")
        limit = subscription.plan.get_limit(key)
        if limit is None:
            return  # ilimitado
        if queryset.count() >= limit:
            raise PlanLimitExceeded(
                f"You have reached the limit of {limit} for '{key}' on your current plan.",
                limit_key=key,
            )


# ─── TenantMembership ─────────────────────────────────────────────────────────


class TenantMembership(models.Model):
    """
    Relaciona usuarios con tenants y opcionalmente con una subsidiaria.

    Los roles NO se definen en el core — cada proyecto define sus propios
    choices en el modelo concreto según su lógica de negocio.

    El mapa de permisos se configura en settings.py del proyecto:

        ROLE_PERMISSIONS = {
            'admin':    {'view_all', 'create', 'update', 'delete'},
            'staff':    {'view_own', 'create', 'update_own'},
            'driver':   {'view_own', 'update_mileage'},
        }

        ROLES_WITH_GLOBAL_VIEW = {'admin', 'manager'}
    """

    # tenant, user y subsidiary se definen con FKs concretas en el proyecto
    role = models.CharField(max_length=30, default="readonly")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        verbose_name = "Membership"
        verbose_name_plural = "Memberships"

    def __str__(self):
        return f"{self.user} → {self.tenant} ({self.role})"

    def has_permission(self, permission):
        """
        Verifica si este rol tiene un permiso específico.
        Lee el mapa de permisos desde settings.ROLE_PERMISSIONS.
        """
        from django.conf import settings

        role_permissions = getattr(settings, "ROLE_PERMISSIONS", {})
        return permission in role_permissions.get(self.role, set())


# ─── TenantAwareModel ─────────────────────────────────────────────────────────


class TenantManager(models.Manager):
    def get_queryset(self):
        tenant = get_current_tenant()
        qs = super().get_queryset()
        return qs.filter(tenant=tenant) if tenant else qs


class TenantAwareModel(models.Model):
    """
    Modelo base para todos los modelos de negocio del proyecto.
    - objects     → filtrado automático por tenant activo en el contexto
    - all_objects → sin filtro, para admin global y tareas de sistema
    """

    objects = TenantManager()
    all_objects = models.Manager()

    def save(self, *args, **kwargs):
        if not self.tenant_id:
            tenant = get_current_tenant()
            if tenant:
                self.tenant = tenant
        super().save(*args, **kwargs)

    class Meta:
        abstract = True
