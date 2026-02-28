# tenant_core/permissions.py
"""
Sistema de permisos basado en roles con filtrado por subsidiaria.

El core provee la infraestructura. Cada proyecto define sus propias
reglas en settings.py:

    ROLE_PERMISSIONS = {
        'admin':   {'view_all', 'create', 'update', 'delete'},
        'staff':   {'view_own', 'create', 'update_own'},
        'driver':  {'view_own', 'update_mileage'},
    }

    ROLES_WITH_GLOBAL_VIEW = {'admin', 'manager'}

    TENANT_MEMBERSHIP_MODEL = 'tenants.TenantMembershipUser'

    IMPERSONATION_GROUPS = ['Vendor', 'SuperAdmin']
"""

from functools import wraps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import PermissionDenied


# ─── Helpers de configuración ─────────────────────────────────────────────────


def get_role_permissions():
    """Lee ROLE_PERMISSIONS desde settings del proyecto."""
    return getattr(settings, "ROLE_PERMISSIONS", {})


def get_roles_with_global_view():
    """Roles que ven todos los registros del tenant (sin filtro de subsidiaria)."""
    return getattr(settings, "ROLES_WITH_GLOBAL_VIEW", set())


def get_impersonation_groups():
    """Grupos de staff autorizados para hacer impersonation."""
    return getattr(settings, "IMPERSONATION_GROUPS", ["SuperAdmin"])


def _get_membership_model():
    """Importación lazy del modelo de membresía para evitar circular imports."""
    from django.apps import apps

    membership_model = getattr(settings, "TENANT_MEMBERSHIP_MODEL", None)
    if not membership_model:
        raise ImproperlyConfigured(
            "Define TENANT_MEMBERSHIP_MODEL in settings.py\n"
            "Example: TENANT_MEMBERSHIP_MODEL = 'tenants.TenantMembershipUser'"
        )
    app_label, model_name = membership_model.split(".")
    return apps.get_model(app_label, model_name)


# ─── Resolvers de rol y subsidiaria ──────────────────────────────────────────


def get_user_role(request):
    """
    Obtiene el rol del usuario desde su membresía.
    Lo cachea en el request para no repetir queries.
    Los usuarios is_staff no tienen rol de membresía — usan Django Groups.
    """
    if hasattr(request, "_user_role"):
        return request._user_role

    if not request.user or not request.user.is_authenticated:
        request._user_role = None
        return None

    if request.user.is_staff:
        request._user_role = None
        return None

    MembershipModel = _get_membership_model()
    try:
        membership = MembershipModel.objects.get(user=request.user, is_active=True)
        request._user_role = membership.role
    except MembershipModel.DoesNotExist:
        request._user_role = None

    return request._user_role


def get_user_subsidiary(request):
    """
    Obtiene la subsidiaria del usuario desde su membresía.
    Lo cachea en el request para no repetir queries.
    Retorna None para staff (ven todo) o usuarios sin subsidiaria asignada.
    """
    if hasattr(request, "_user_subsidiary"):
        return request._user_subsidiary

    if request.user.is_staff:
        request._user_subsidiary = None
        return None

    MembershipModel = _get_membership_model()
    try:
        membership = MembershipModel.objects.select_related("subsidiary").get(
            user=request.user, is_active=True
        )
        request._user_subsidiary = getattr(membership, "subsidiary", None)
    except MembershipModel.DoesNotExist:
        request._user_subsidiary = None

    return request._user_subsidiary


def has_permission(request, permission):
    """
    Verifica si el usuario tiene un permiso específico según su rol.

    Uso:
        if not has_permission(request, 'create'):
            raise PermissionDenied
    """
    role = get_user_role(request)
    if role is None:
        return False
    return permission in get_role_permissions().get(role, set())


def user_in_group(user, *groups):
    """
    Verifica si un usuario staff pertenece a alguno de los grupos indicados.
    Los superusuarios siempre retornan True.

    Uso:
        if not user_in_group(request.user, 'Administrator', 'SuperAdmin'):
            raise PermissionDenied
    """
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=groups).exists()


def can_impersonate(user):
    """
    Verifica si el usuario staff puede hacer impersonation de un tenant.
    Lee los grupos permitidos desde settings.IMPERSONATION_GROUPS.
    """
    if not user.is_staff:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=get_impersonation_groups()).exists()


# ─── Mixin para ViewSets ──────────────────────────────────────────────────────


class RoleFilterMixin:
    """
    Filtra el queryset automáticamente según el rol del usuario:
    - Roles con vista global → ven todos los registros del tenant
    - Roles operativos       → solo ven los de su subsidiaria

    Uso:
        class VehicleViewSet(RoleFilterMixin, TenantQuerysetMixin, viewsets.ModelViewSet):
            subsidiary_field = 'subsidiary'  # nombre del campo FK en el modelo
    """

    subsidiary_field = "subsidiary"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Staff (incluyendo impersonation) ve todo
        if user.is_staff:
            return qs

        role = get_user_role(self.request)

        if role in get_roles_with_global_view():
            return qs

        # Roles operativos: filtrar por subsidiaria asignada
        subsidiary = get_user_subsidiary(self.request)
        if subsidiary:
            return qs.filter(**{self.subsidiary_field: subsidiary})

        return qs.none()


# ─── Decoradores ─────────────────────────────────────────────────────────────


def require_permission(permission):
    """
    Verifica que el usuario tenga el permiso antes de ejecutar la acción.
    Compatible con métodos de ViewSet y vistas de función.

    Uso en ViewSet:
        @require_permission('delete')
        def destroy(self, request, *args, **kwargs): ...

    Uso en vista de función:
        @require_permission('create')
        def create_vehicle(request): ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self_or_request, *args, **kwargs):
            request = getattr(self_or_request, "request", self_or_request)
            if not has_permission(request, permission):
                role = get_user_role(request) or "no role"
                raise PermissionDenied(
                    f"Your role '{role}' does not have permission to perform this action."
                )
            return view_func(self_or_request, *args, **kwargs)

        return wrapper

    return decorator


def roles_required(*roles):
    """
    Restringe el acceso a roles específicos del tenant.

    Uso:
        @roles_required('admin', 'manager')
        def authorize_maintenance(self, request, pk=None): ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self_or_request, *args, **kwargs):
            request = getattr(self_or_request, "request", self_or_request)
            role = get_user_role(request)
            if role not in roles:
                raise PermissionDenied(
                    f"This action requires one of these roles: {', '.join(roles)}."
                )
            return view_func(self_or_request, *args, **kwargs)

        return wrapper

    return decorator


def groups_required(*groups):
    """
    Restringe el acceso a grupos de Django (usuarios staff/internos).

    Uso:
        @groups_required('Administrator', 'SuperAdmin')
        def create_tenant(self, request): ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self_or_request, *args, **kwargs):
            request = getattr(self_or_request, "request", self_or_request)
            if not user_in_group(request.user, *groups):
                raise PermissionDenied(
                    f"Requires one of these groups: {', '.join(groups)}."
                )
            return view_func(self_or_request, *args, **kwargs)

        return wrapper

    return decorator
