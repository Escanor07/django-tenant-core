# django-tenant-core

Base multi-tenant para proyectos Django B2B. Resuelve el tenant desde JWT, controla suscripciones, límites por plan y permisos por rol con filtrado por subsidiaria.

## Instalación

```bash
pip install git+https://github.com/Escanor07/django-tenant-core.git@v0.1.0
```

---

## Configuración rápida

```python
# settings.py
INSTALLED_APPS = [
    ...
    'rest_framework_simplejwt.token_blacklist',
    'tenant_core',
    'usuarios',   # antes que tenants
    'tenants',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'tenants.middleware.AppTenantMiddleware',  # segundo, antes de sessions
    ...
]

AUTH_USER_MODEL = 'usuarios.CustomUser'

# ── Tenant ────────────────────────────────────────────────────────────────────
TENANT_MEMBERSHIP_MODEL = 'tenants.TenantMembershipUser'

# ── Roles del tenant (flujo de trabajo, definidos por proyecto) ───────────────
ROLE_PERMISSIONS = {
    'administrador': {'view_all', 'create', 'update', 'delete'},
    'direccion':     {'view_all', 'view_dashboard', 'authorize'},
    'staff':         {'view_own', 'create', 'update_own'},
    'conductor':     {'view_own', 'update_km'},
}
ROLES_WITH_GLOBAL_VIEW = {'administrador', 'direccion'}

# ── Grupos de staff (panel interno, definidos por proyecto) ───────────────────
STAFF_GROUPS = {
    'SuperAdmin':    [],
    'Administrador': ['can_create_tenant', 'can_view_subscriptions', 'can_create_staff_user'],
    'Vendedor':      ['can_impersonate_tenant'],
    'Tester':        ['can_access_beta_features'],
    'Desarrollador': ['can_access_debug_mode'],
}
IMPERSONATION_GROUPS = ['Vendedor', 'SuperAdmin']
```

---

## Dos capas de permisos

```
┌─────────────────────────────────────────────────────────────┐
│  CAPA 1 — Django Groups (usuarios staff/internos)           │
│                                                             │
│  SuperAdmin    → todo                                       │
│  Administrador → crear tenants, ver suscripciones           │
│  Vendedor      → impersonation de tenants                   │
│  Tester        → features en beta                           │
│  Desarrollador → modo debug                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  CAPA 2 — Roles en Membership (usuarios del tenant)         │
│  Definidos por cada proyecto en settings.ROLE_PERMISSIONS   │
│                                                             │
│  administrador → dueño del tenant, acceso total             │
│  direccion     → autoriza y ve dashboards                   │
│  staff         → crea y agenda servicios                    │
│  conductor     → actualiza kilometrajes                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementación paso a paso

### 1. Modelos del proyecto

```python
# tenants/models.py
from django.db import models
from django.conf import settings
from tenant_core.models import Tenant, Plan, Subscription, TenantMembership, TenantAwareModel


class MiPlan(Plan):
    PLAN_CHOICES = [('free', 'Free'), ('pro', 'Pro'), ('enterprise', 'Enterprise')]
    name = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True)

    class Meta:
        verbose_name = 'Plan'


class MiTenant(Tenant):
    # Agrega campos propios del negocio
    rfc  = models.CharField(max_length=13, blank=True)
    logo = models.URLField(blank=True, null=True)

    class Meta:
        verbose_name = 'Empresa'


class MiSuscripcion(Subscription):
    tenant = models.ForeignKey(MiTenant,  on_delete=models.CASCADE, related_name='suscripciones')
    plan   = models.ForeignKey(MiPlan,    on_delete=models.PROTECT)


class Subsidiary(TenantAwareModel):
    tenant  = models.ForeignKey(MiTenant, on_delete=models.CASCADE, related_name='subsidiaries')
    name    = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)


class TenantMembershipUser(TenantMembership):
    ROL_CHOICES = [
        ('administrador', 'Administrador'),
        ('direccion',     'Dirección'),
        ('staff',         'Staff'),
        ('conductor',     'Conductor'),
    ]
    tenant     = models.ForeignKey(MiTenant, on_delete=models.CASCADE, related_name='memberships')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memberships')
    subsidiary = models.ForeignKey(Subsidiary, on_delete=models.SET_NULL, null=True, blank=True)
    rol        = models.CharField(max_length=30, choices=ROL_CHOICES, default='staff')

    class Meta:
        unique_together = [('tenant', 'user')]
```

### 2. Middleware del proyecto

```python
# tenants/middleware.py
from tenant_core.middleware import TenantMiddleware
from tenant_core.exceptions import TenantNotFound, TenantInactive
from tenant_core.permissions import can_impersonate
from .models import TenantMembershipUser, MiTenant


class AppTenantMiddleware(TenantMiddleware):

    PUBLIC_PATHS = TenantMiddleware.PUBLIC_PATHS + [
        '/api/admin/tenants/',
        '/api/admin/planes/',
    ]

    def __call__(self, request):
        self.request = request
        return super().__call__(request)

    def _get_tenant_for_user(self, user):
        if user.is_staff:
            return self._resolver_impersonation()
        return self._resolver_usuario_normal(user)

    def _resolver_usuario_normal(self, user):
        try:
            membership = (
                TenantMembershipUser.objects
                .select_related('tenant')
                .get(user=user, is_active=True)
            )
            return membership.tenant
        except TenantMembershipUser.DoesNotExist:
            raise TenantNotFound()
        except TenantMembershipUser.MultipleObjectsReturned:
            return (
                TenantMembershipUser.objects
                .select_related('tenant')
                .filter(user=user, is_active=True)
                .order_by('-created_at')
                .first()
                .tenant
            )

    def _resolver_impersonation(self):
        tenant_id = self.request.headers.get('X-Tenant-ID')
        if not tenant_id:
            return None

        # Verifica que el staff tenga permiso de impersonation
        if not can_impersonate(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("No tienes permiso para acceder como tenant.")

        try:
            tenant = MiTenant.objects.get(id=tenant_id)
        except (MiTenant.DoesNotExist, ValueError):
            raise TenantNotFound()

        if not tenant.is_active:
            raise TenantInactive()

        self.request.is_impersonating = True
        return tenant
```

### 3. ViewSets con permisos por rol

```python
# vehiculos/views.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from tenant_core.mixins import TenantRequiredMixin, TenantQuerysetMixin
from tenant_core.permissions import (
    RoleFilterMixin, require_permission, roles_required, groups_required
)


class VehiculoViewSet(TenantRequiredMixin, RoleFilterMixin, TenantQuerysetMixin,
                      viewsets.ModelViewSet):
    """
    - administrador/direccion → ven todos los vehículos del tenant
    - staff/conductor         → solo los de su subsidiaria
    """
    queryset         = Vehiculo.objects.all()
    serializer_class = VehiculoSerializer
    subsidiary_field = 'subsidiary'

    @require_permission('create')
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @require_permission('delete')
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    @roles_required('administrador', 'direccion')
    def autorizar(self, request, pk=None):
        # Solo administrador y dirección pueden autorizar
        ...


# Panel interno — solo staff con grupo correcto
class TenantAdminViewSet(viewsets.ModelViewSet):

    @groups_required('Administrador', 'SuperAdmin')
    def create(self, request, *args, **kwargs):
        # Solo Administrador y SuperAdmin pueden crear tenants
        return super().create(request, *args, **kwargs)
```

### 4. Crear grupos de staff

```bash
# Correr una sola vez al hacer deploy
python manage.py setup_staff_groups

# Output:
#   + Grupo creado: SuperAdmin
#   + Grupo creado: Administrador
#   + Grupo creado: Vendedor
#   + Grupo creado: Tester
#   + Grupo creado: Desarrollador
#   ✓ 5 grupos creados, 0 actualizados.
```

### 5. Crear un tenant desde CLI

```bash
# En el proyecto, hereda el comando base:
# tenants/management/commands/create_tenant.py

from tenant_core.management.commands.create_tenant import BaseCreateTenantCommand
from tenants.models import MiTenant, MiPlan, MiSuscripcion, TenantMembershipUser
from django.contrib.auth import get_user_model

class Command(BaseCreateTenantCommand):
    def handle(self, *args, **options):
        self.crear_tenant_completo(
            TenantModel=MiTenant,
            PlanModel=MiPlan,
            SubscriptionModel=MiSuscripcion,
            MembershipModel=TenantMembershipUser,
            UserModel=get_user_model(),
            options=options,
        )

# Uso:
python manage.py create_tenant \
    --name "Empresa Demo" \
    --slug empresa-demo \
    --plan pro \
    --email admin@empresa.com \
    --password segura123 \
    --dias 30
```

---

## Referencia de componentes

| Componente | Archivo | Descripción |
|---|---|---|
| `Tenant` | `models.py` | Modelo base abstracto del cliente B2B |
| `Plan` | `models.py` | Planes con límites en DB (JSONField) |
| `Subscription` | `models.py` | Vigencia y estado de pago |
| `TenantMembership` | `models.py` | Usuario ↔ Tenant con rol (sin roles hardcodeados) |
| `TenantAwareModel` | `models.py` | Modelos de negocio con filtrado automático |
| `TenantMiddleware` | `middleware.py` | JWT → tenant → verifica suscripción |
| `TenantRequiredMixin` | `mixins.py` | Bloquea si no hay tenant activo |
| `TenantQuerysetMixin` | `mixins.py` | Segunda capa de filtrado por tenant |
| `PlanLimitMixin` | `mixins.py` | Verifica límites antes de crear |
| `RoleFilterMixin` | `permissions.py` | Filtra por subsidiaria según rol |
| `require_permission` | `permissions.py` | Decorador — verifica permiso por rol del tenant |
| `roles_required` | `permissions.py` | Decorador — restringe a roles específicos del tenant |
| `groups_required` | `permissions.py` | Decorador — restringe a grupos de staff de Django |
| `can_impersonate` | `permissions.py` | Verifica si el staff puede hacer impersonation |
| `setup_staff_groups` | management command | Crea los grupos de Django desde settings |
| `create_tenant` | management command | Base para crear tenants desde CLI |

---

## Desarrollo

```bash
git clone git@github.com:Escanor07/django-tenant-core.git
pip install -e ".[dev]"
pytest tests/ -v
coverage run -m pytest && coverage report
```

## Versionado

`MAJOR.MINOR.PATCH` — ver [CHANGELOG](https://github.com/Escanor07/django-tenant-core/blob/main/CHANGELOG.md)