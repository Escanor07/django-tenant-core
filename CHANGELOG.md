# Changelog

Todos los cambios notables se documentan aquí.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).

---

## [0.1.0] - 2026-02-18

### Agregado
- `Tenant` modelo base abstracto
- `Plan` con límites configurables via `limites_extra` (JSONField)
- `Subscription` con vigencia, estado de pago y validación de acceso
- `TenantMembership` para relacionar usuarios con tenants y roles
- `TenantAwareModel` con `TenantManager` y auto-asignación de tenant en `save()`
- `TenantMiddleware` base con resolución via JWT
- `TenantRequiredMixin`, `TenantQuerysetMixin`, `PlanLimitMixin`, `AdminOrTenantMixin`
- Decoradores `@tenant_required`, `@plan_limit`, `@staff_only`
- `TenantAwareAdmin` y `GlobalAdmin` para el panel de Django Admin
- Comando base `create_tenant` para CLI
- Suite de tests con pytest y fixtures compartidos
- Pipeline CI/CD con GitHub Actions
