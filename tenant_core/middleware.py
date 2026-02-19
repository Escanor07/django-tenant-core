# tenant_core/middleware.py
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from .context import set_current_tenant, clear_current_tenant
from .exceptions import (
    TenantNotFound, TenantInactive,
    SubscriptionExpired, SubscriptionSuspended
)


class TenantMiddleware:
    """
    Middleware base que:
    1. Autentica el JWT del request
    2. Resuelve el tenant desde el usuario autenticado
    3. Verifica que la suscripción esté vigente
    4. Inyecta el tenant en el contexto del thread

    Los proyectos heredan este middleware e implementan _get_tenant_for_user().
    Las rutas públicas (login, registro) se declaran en PUBLIC_PATHS.
    """

    # Rutas que no requieren tenant (login, registro, healthcheck, etc.)
    # Los proyectos pueden sobreescribir esto
    PUBLIC_PATHS = [
        '/api/auth/login/',
        '/api/auth/register/',
        '/api/auth/token/refresh/',
        '/admin/',
        '/health/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    def __call__(self, request):
        if self._is_public(request.path):
            return self.get_response(request)

        try:
            user = self._authenticate_jwt(request)

            # Admins globales (is_staff) saltan la resolución de tenant
            if user and user.is_staff:
                request.tenant = None
                # No se setea tenant en contexto — tienen acceso a todo
                return self.get_response(request)

            if not user:
                return JsonResponse({'error': 'Autenticación requerida.'}, status=401)

            tenant = self._get_tenant_for_user(user)
            if not tenant.is_active:
                raise TenantInactive()

            # Verifica suscripción — lanza excepción si no está vigente
            tenant.verificar_suscripcion()

            request.tenant = tenant
            set_current_tenant(tenant)

            response = self.get_response(request)

        except TenantNotFound:
            return JsonResponse({'error': 'No tienes una empresa asociada.'}, status=404)
        except TenantInactive:
            return JsonResponse({'error': 'Tu cuenta está desactivada.'}, status=403)
        except SubscriptionExpired as e:
            return JsonResponse({'error': str(e), 'code': 'subscription_expired'}, status=402)
        except SubscriptionSuspended as e:
            return JsonResponse({'error': str(e), 'code': 'subscription_suspended'}, status=402)
        except Exception as e:
            raise  # deja que Django maneje errores inesperados normalmente
        finally:
            clear_current_tenant()

        return response

    def _authenticate_jwt(self, request):
        """Extrae y valida el JWT. Retorna el user o None."""
        try:
            result = self.jwt_auth.authenticate(request)
            if result is None:
                return None
            user, token = result
            return user
        except (InvalidToken, TokenError):
            return None

    def _is_public(self, path):
        return any(path.startswith(p) for p in self.PUBLIC_PATHS)

    def _get_tenant_for_user(self, user):
        """
        Implementar en el proyecto.
        Debe retornar el Tenant correspondiente al usuario
        o lanzar TenantNotFound si no tiene ninguno.
        """
        raise NotImplementedError(
            "Implementa _get_tenant_for_user(user) en tu middleware del proyecto."
        )
