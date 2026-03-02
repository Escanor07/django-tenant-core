# tenant_core/management/commands/setup_staff_groups.py
"""
Crea los grupos de Django para usuarios staff internos.
Correr una vez al hacer deploy o al agregar nuevos grupos.

Uso:
    python manage.py setup_staff_groups

Los grupos se configuran en settings.py del proyecto:

    STAFF_GROUPS = {
        'SuperAdmin':    [],
        'Administrator': [
            'can_create_tenant',
            'can_view_subscriptions',
            'can_create_staff_user',
        ],
        'Vendor': [
            'can_impersonate_tenant',
        ],
        'Tester': [
            'can_access_beta_features',
        ],
        'Developer': [
            'can_access_debug_mode',
        ],
    }
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.conf import settings


class Command(BaseCommand):
    help = "Creates or updates staff groups defined in settings.STAFF_GROUPS"

    def handle(self, *args, **options):
        staff_groups = getattr(settings, "STAFF_GROUPS", {})

        if not staff_groups:
            self.stdout.write(
                self.style.WARNING(
                    "STAFF_GROUPS not found in settings.py\n"
                    "Define the groups before running this command."
                )
            )
            return

        created_count = 0
        updated_count = 0

        for group_name, permissions in staff_groups.items():
            group, created = Group.objects.get_or_create(name=group_name)

            if created:
                created_count += 1
                self.stdout.write(f"  + Group created: {group_name}")
            else:
                updated_count += 1
                self.stdout.write(f"  ~ Group updated: {group_name}")

            for perm_codename in permissions:
                perm = self._get_or_create_permission(perm_codename)
                if perm:
                    group.permissions.add(perm)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ {created_count} groups created, {updated_count} updated."
            )
        )

    def _get_or_create_permission(self, codename):
        """Obtiene o crea un permiso custom."""
        try:
            return Permission.objects.get(codename=codename)
        except Permission.DoesNotExist:
            ct, _ = ContentType.objects.get_or_create(
                app_label="tenant_core",
                model="staffpermission",
            )
            perm, _ = Permission.objects.get_or_create(
                codename=codename,
                content_type=ct,
                defaults={"name": codename.replace("_", " ").title()},
            )
            return perm
