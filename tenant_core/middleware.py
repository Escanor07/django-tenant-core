# tenant_core/middleware.py
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from .context import set_current_tenant, clear_current_tenant
from .exceptions import (
    TenantNotFound,
    TenantInactive,
    SubscriptionExpired,
    SubscriptionSuspended,
)


class TenantMiddleware:
    """
    Middleware base. Flujos soportados:

    Usuario normal:
        JWT → user → _get_tenant_for_user() → verifica suscripción → contexto

    Staff sin X-Tenant-ID:
        JWT → user.is_staff=True → acceso global sin tenant

    Staff con X-Tenant-ID (impersonation):
        JWT → user.is_staff=True → verifica grupo → carga tenant → contexto
        (sin verificar suscripción — permite soporte a cuentas vencidas)

    Los proyectos implementan _get_tenant_for_user().
    """

    PUBLIC_PATHS = [
        "/api/auth/login/",
        "/api/auth/token/refresh/",
        "/api/auth/register/",
        "/admin/",
        "/health/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    def __call__(self, request):
        request.is_impersonating = False

        if self._is_public(request.path):
            return self.get_response(request)

        try:
            user = self._authenticate_jwt(request)

            if not user:
                return JsonResponse({"error": "Authentication required."}, status=401)

            # Staff sin impersonation → acceso global sin filtro de tenant
            if user.is_staff and not self._has_impersonation_header(request):
                request.tenant = None
                return self.get_response(request)

            tenant = self._get_tenant_for_user(user)

            if tenant is None:
                request.tenant = None
                return self.get_response(request)

            if not tenant.is_active:
                raise TenantInactive()

            # No verificar suscripción en impersonation — el staff
            # necesita poder entrar aunque la cuenta esté vencida
            if not request.is_impersonating:
                tenant.verify_subscription()

            request.tenant = tenant
            set_current_tenant(tenant)

            response = self.get_response(request)

        except TenantNotFound:
            return JsonResponse(
                {"error": "No tenant associated with this account."}, status=404
            )
        except TenantInactive:
            return JsonResponse({"error": "This account is deactivated."}, status=403)
        except SubscriptionExpired as e:
            return JsonResponse(
                {"error": str(e), "code": "subscription_expired"}, status=402
            )
        except SubscriptionSuspended as e:
            return JsonResponse(
                {"error": str(e), "code": "subscription_suspended"}, status=402
            )
        finally:
            clear_current_tenant()

        return response

    def _authenticate_jwt(self, request):
        try:
            result = self.jwt_auth.authenticate(request)
            if result is None:
                return None
            user, _ = result
            return user
        except (InvalidToken, TokenError):
            return None

    def _is_public(self, path):
        return any(path.startswith(p) for p in self.PUBLIC_PATHS)

    def _has_impersonation_header(self, request):
        return bool(request.headers.get("X-Tenant-ID"))

    def _get_tenant_for_user(self, user):
        """
        Implementar en el proyecto.
        Debe retornar el Tenant del usuario o lanzar TenantNotFound.
        Para staff con impersonation, marcar request.is_impersonating = True.
        """
        raise NotImplementedError(
            "Implement _get_tenant_for_user(user) in your project middleware."
        )
