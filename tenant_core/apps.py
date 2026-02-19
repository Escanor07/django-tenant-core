# tenant_core/apps.py
from django.apps import AppConfig


class TenantCoreConfig(AppConfig):
    name    = "tenant_core"
    label   = "tenant_core"
    verbose_name = "Tenant Core"

    def ready(self):
        pass  # aquí se pueden conectar signals en el futuro
