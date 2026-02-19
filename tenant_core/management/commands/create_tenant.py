# tenant_core/management/commands/create_tenant.py
"""
Comando de utilidad para crear tenants desde la CLI.
Cada proyecto hereda y sobreescribe handle() si necesita campos extra.

Uso:
    python manage.py create_tenant \
        --name "Empresa Demo" \
        --slug empresa-demo \
        --plan free \
        --admin-email admin@empresa.com
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class BaseCreateTenantCommand(BaseCommand):
    help = "Crea un nuevo tenant con suscripción inicial"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Nombre de la empresa")
        parser.add_argument(
            "--slug", required=True, help="Slug único (ej: empresa-demo)"
        )
        parser.add_argument(
            "--plan", default="free", help="Plan inicial: free|pro|enterprise"
        )
        parser.add_argument(
            "--admin-email", required=True, help="Email del usuario owner"
        )
        parser.add_argument(
            "--dias", default=30, type=int, help="Duración inicial en días"
        )

    def handle(self, *args, **options):
        self.stdout.write("Implementa handle() en el comando de tu proyecto.")
        self.stdout.write("Consulta la documentación en docs/commands.md")
