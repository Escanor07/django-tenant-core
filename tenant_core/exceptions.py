# tenant_core/exceptions.py


class TenantNotFound(Exception):
    """No se encontró tenant para el usuario autenticado."""
    pass


class TenantInactive(Exception):
    """El tenant existe pero está desactivado."""
    pass


class SubscriptionExpired(Exception):
    """La suscripción del tenant ha vencido."""
    pass


class SubscriptionSuspended(Exception):
    """La suscripción está suspendida por falta de pago u otro motivo."""
    pass


class PlanLimitExceeded(Exception):
    """Se alcanzó un límite del plan actual."""
    def __init__(self, message="Límite del plan alcanzado", limit_key=None):
        self.limit_key = limit_key  # ej: 'max_vehiculos', 'max_usuarios'
        super().__init__(message)
