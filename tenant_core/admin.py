# tenant_core/admin.py
from django.contrib import admin
from .context import get_current_tenant


class TenantAwareAdmin(admin.ModelAdmin):
    """
    Admin que filtra automáticamente por tenant activo.
    Para el panel de cada empresa (no el superadmin global).
    """
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        tenant = get_current_tenant()
        if tenant:
            return qs.filter(tenant=tenant)
        return qs

    def save_model(self, request, obj, form, commit):
        if not obj.tenant_id:
            obj.tenant = get_current_tenant()
        super().save_model(request, obj, form, commit)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filtra los dropdowns de FK para mostrar solo los del tenant actual."""
        tenant = get_current_tenant()
        if tenant and hasattr(db_field.related_model, 'tenant'):
            kwargs["queryset"] = db_field.related_model.objects.filter(tenant=tenant)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class GlobalAdmin(admin.ModelAdmin):
    """
    Admin sin filtro de tenant. Solo para superusuarios.
    Muestra una columna extra con el nombre del tenant.
    """
    def get_queryset(self, request):
        # Usa all_objects para evitar el TenantManager
        return self.model.all_objects.all()
