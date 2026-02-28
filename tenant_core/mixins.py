# tenant_core/mixins.py
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from .context import get_current_tenant
from .exceptions import PlanLimitExceeded


class TenantRequiredMixin:
    """
    Bloquea el acceso si no hay tenant activo en el contexto.
    Compatible con Django CBVs y DRF ViewSets/APIViews.
    """

    def dispatch(self, request, *args, **kwargs):
        if not get_current_tenant() and not getattr(request.user, "is_staff", False):
            raise DRFPermissionDenied("An active tenant is required.")
        return super().dispatch(request, *args, **kwargs)


class TenantQuerysetMixin:
    """
    Segunda capa de seguridad: filtra el queryset por tenant en la vista.
    Complementa al TenantManager del modelo.
    Usar siempre junto a TenantRequiredMixin.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant and hasattr(qs.model, "tenant"):
            return qs.filter(tenant=tenant)
        return qs


class PlanLimitMixin:
    """
    Verifica los límites del plan antes de crear un objeto.

    Uso en el ViewSet:
        class VehicleViewSet(PlanLimitMixin, ...):
            plan_limit_key = 'max_vehicles'

            def get_plan_limit_queryset(self):
                return Vehicle.objects.all()  # ya filtrado por tenant
    """

    plan_limit_key = None

    def get_plan_limit_queryset(self):
        """Sobreescribir para retornar el queryset a contar."""
        raise NotImplementedError("Define get_plan_limit_queryset() in your ViewSet.")

    def perform_create(self, serializer):
        tenant = get_current_tenant()
        if self.plan_limit_key and tenant:
            try:
                tenant.verify_limit(self.plan_limit_key, self.get_plan_limit_queryset())
            except PlanLimitExceeded as e:
                raise DRFPermissionDenied(str(e))
        super().perform_create(serializer)


class AdminOrTenantMixin:
    """
    Permite acceso total a is_staff.
    Para usuarios normales, aplica filtro de tenant.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return qs
        tenant = get_current_tenant()
        if tenant:
            return qs.filter(tenant=tenant)
        return qs.none()
