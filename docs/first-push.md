# Primer push a GitHub

Comandos exactos para subir el repo por primera vez.

## 1. Crea el repo en GitHub

Ve a https://github.com/organizations/Escanor07/repositories/new (o tu perfil personal)
y crea un repo llamado `django-tenant-core` como **privado**. No inicialices con README.

## 2. Inicializa git y sube

```bash
cd django-tenant-core

git init
git add .
git commit -m "feat: initial release v0.1.0

- Tenant base abstracto
- Plan con límites configurables (JSONField)
- Subscription con vigencia y estado de pago
- TenantMembership usuario <-> tenant con roles
- TenantAwareModel con TenantManager
- TenantMiddleware base con resolución via JWT
- Mixins: TenantRequired, TenantQueryset, PlanLimit, AdminOrTenant
- Decoradores: @tenant_required, @plan_limit, @staff_only
- Suite de tests con pytest
- Pipeline CI/CD con GitHub Actions"

git branch -M main
git remote add origin git@github.com:Escanor07/django-tenant-core.git
git push -u origin main
```

## 3. Crea el primer tag de release

```bash
git tag v0.1.0
git push origin v0.1.0
```

Esto dispara el job `release` del CI que construye el `.whl` y lo adjunta al GitHub Release automáticamente.

## 4. Protege la rama main (recomendado)

En GitHub → Settings → Branches → Add branch protection rule:

- Branch name pattern: `main`
- ✅ Require a pull request before merging
- ✅ Require status checks to pass (selecciona el job `test`)
- ✅ Do not allow bypassing the above settings

Así nadie (ni tú) puede pushear directo a `main` sin pasar los tests.
