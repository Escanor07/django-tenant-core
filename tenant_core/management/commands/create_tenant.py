# tenant_core/management/commands/create_tenant.py
"""
Comando base para crear tenants desde la CLI.
Cada proyecto hereda e implementa handle() con sus modelos concretos.

Uso en el proyecto:
    # tenants/management/commands/create_tenant.py
    from tenant_core.management.commands.create_tenant import BaseCreateTenantCommand
    from tenants.models import MyTenant, MyPlan, MySubscription, TenantMembershipUser
    from django.contrib.auth import get_user_model

    class Command(BaseCreateTenantCommand):
        def handle(self, *args, **options):
            self.create_full_tenant(
                TenantModel=MyTenant,
                PlanModel=MyPlan,
                SubscriptionModel=MySubscription,
                MembershipModel=TenantMembershipUser,
                UserModel=get_user_model(),
                options=options,
            )

    # Uso:
    # python manage.py create_tenant \\
    #     --name "Demo Company" \\
    #     --slug demo-company \\
    #     --plan pro \\
    #     --email admin@company.com \\
    #     --password secret123 \\
    #     --days 30
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db import transaction


class BaseCreateTenantCommand(BaseCommand):
    help = "Creates a new tenant with plan, subscription and owner user"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Tenant name")
        parser.add_argument(
            "--slug", required=True, help="Unique slug (e.g. demo-company)"
        )
        parser.add_argument("--plan", required=True, help="Plan name (e.g. free, pro)")
        parser.add_argument("--email", required=True, help="Owner user email")
        parser.add_argument("--password", required=True, help="Owner user password")
        parser.add_argument(
            "--days", default=30, type=int, help="Subscription duration in days"
        )
        parser.add_argument(
            "--owner-role", default="admin", help="Owner role in the tenant"
        )

    def create_full_tenant(
        self,
        TenantModel,
        PlanModel,
        SubscriptionModel,
        MembershipModel,
        UserModel,
        options,
    ):
        with transaction.atomic():
            # 1. Verificar que el plan exista
            try:
                plan = PlanModel.objects.get(name=options["plan"])
            except PlanModel.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(
                        f"Plan '{options['plan']}' not found. "
                        f"Available plans: {list(PlanModel.objects.values_list('name', flat=True))}"
                    )
                )
                return

            # 2. Crear el tenant
            tenant = TenantModel.objects.create(
                name=options["name"],
                slug=options["slug"],
            )
            self.stdout.write(f"  Tenant created: {tenant.name}")

            # 3. Crear suscripción inicial
            SubscriptionModel.objects.create(
                tenant=tenant,
                plan=plan,
                start_date=timezone.now().date(),
                end_date=timezone.now().date() + timedelta(days=options["days"]),
                status="active",
            )
            self.stdout.write(
                f"  Subscription created: {plan.name} for {options['days']} days"
            )

            # 4. Crear usuario owner
            user = UserModel.objects.create_user(
                email=options["email"],
                password=options["password"],
            )
            self.stdout.write(f"  User created: {user.email}")

            # 5. Crear membresía
            MembershipModel.objects.create(
                tenant=tenant,
                user=user,
                role=options["owner_role"],
            )
            self.stdout.write(
                f"  Membership created with role: {options['owner_role']}"
            )

        self.stdout.write(
            self.style.SUCCESS(f"\n✓ Tenant '{tenant.name}' created successfully.")
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "Implement handle() in your project command.\n"
                "See docs/install.md for reference."
            )
        )
