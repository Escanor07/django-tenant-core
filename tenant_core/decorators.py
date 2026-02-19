# tenant_core/decorators.py
from functools import wraps
from rest_framework.exceptions import PermissionDenied
from .context import get_current_tenant
from .exceptions import PlanLimitExceeded


def tenant_required(view_func):
    """
    Bloquea la vista si no hay tenant activo en el contexto.
    Para vistas de función (no CBV).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not get_current_tenant() and not request.user.is_staff:
            raise PermissionDenied("Se requiere un tenant activo.")
        return view_func(request, *args, **kwargs)
    return wrapper


def plan_limit(key, get_queryset_func):
    """
    Decorador para verificar límites del plan en vistas de función.

    Uso:
        @tenant_required
        @plan_limit('max_vehiculos', lambda req: Vehiculo.objects.all())
        def crear_vehiculo(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            tenant = get_current_tenant()
            if tenant:
                try:
                    qs = get_queryset_func(request)
                    tenant.verificar_limite(key, qs)
                except PlanLimitExceeded as e:
                    raise PermissionDenied(str(e))
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def staff_only(view_func):
    """
    Solo admins globales (is_staff) pueden acceder.
    Para endpoints de gestión de tenants, suscripciones, etc.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user or not request.user.is_staff:
            raise PermissionDenied("Solo administradores globales pueden acceder.")
        return view_func(request, *args, **kwargs)
    return wrapper
