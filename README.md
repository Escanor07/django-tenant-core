# django-tenant-core

Base multi-tenant para proyectos Django B2B. Resuelve el tenant desde JWT → usuario → membresía, controla suscripciones y límites por plan.

## Instalación

```bash
# Desde el repositorio privado
pip install git+https://github.com/tu-org/django-tenant-core.git@v0.1.0
```

## Configuración rápida

```python
# settings.py
INSTALLED_APPS = [
    ...
    "tenant_core",
    "tu_app.tenants",
]

MIDDLEWARE = [
    ...
    "tu_app.tenants.middleware.TuTenantMiddleware",  # antes de los demás
    ...
]
```

## Uso básico

### 1. Extender los modelos base

```python
from tenant_core.models import Tenant, Plan, Subscription, TenantMembership, TenantAwareModel

class MiEmpresa(Tenant): ...
class MiPlan(Plan): ...
class MiSuscripcion(Subscription):
    tenant = models.ForeignKey(MiEmpresa, ...)
    plan   = models.ForeignKey(MiPlan, ...)
class MiMembership(TenantMembership):
    tenant = models.ForeignKey(MiEmpresa, ...)
    user   = models.ForeignKey(settings.AUTH_USER_MODEL, ...)

class MiModelo(TenantAwareModel):
    tenant = models.ForeignKey(MiEmpresa, on_delete=models.CASCADE)
    ...
```

### 2. Implementar el middleware

```python
from tenant_core.middleware import TenantMiddleware
from tenant_core.exceptions import TenantNotFound

class MiMiddleware(TenantMiddleware):
    def _get_tenant_for_user(self, user):
        try:
            return MiMembership.objects.get(user=user, is_active=True).tenant
        except MiMembership.DoesNotExist:
            raise TenantNotFound()
```

### 3. Usar en ViewSets

```python
from tenant_core.mixins import TenantRequiredMixin, TenantQuerysetMixin, PlanLimitMixin

class MiViewSet(TenantRequiredMixin, PlanLimitMixin, TenantQuerysetMixin, viewsets.ModelViewSet):
    plan_limit_key = "max_registros"
    def get_plan_limit_queryset(self):
        return MiModelo.objects.all()
```

## Componentes

| Componente | Descripción |
|---|---|
| `Tenant` | Modelo base abstracto del cliente B2B |
| `Plan` | Planes con límites en DB (`limites_extra` JSONField) |
| `Subscription` | Vigencia, estado de pago, verificación de acceso |
| `TenantMembership` | Usuario ↔ Tenant con rol |
| `TenantAwareModel` | Modelos de negocio con filtrado automático por tenant |
| `TenantMiddleware` | JWT → user → tenant → verifica suscripción |
| `TenantRequiredMixin` | Bloquea vistas si no hay tenant activo |
| `TenantQuerysetMixin` | Segunda capa de filtrado en `get_queryset()` |
| `PlanLimitMixin` | Verifica límites antes de crear registros |
| `AdminOrTenantMixin` | Admins `is_staff` ven todo; usuarios ven su tenant |

## Desarrollo

```bash
git clone https://github.com/tu-org/django-tenant-core
pip install -e ".[dev]"
pytest tests/ -v
coverage run -m pytest && coverage report
```

## Versionado

`MAJOR.MINOR.PATCH` — ver [CHANGELOG](CHANGELOG.md)
