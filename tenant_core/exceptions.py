# tenant_core/exceptions.py


class TenantNotFound(Exception):
    """El usuario autenticado no tiene tenant asociado."""

    pass


class TenantInactive(Exception):
    """El tenant existe pero está desactivado."""

    pass


class SubscriptionExpired(Exception):
    """La suscripción del tenant ha vencido o no existe."""

    pass


class SubscriptionSuspended(Exception):
    """La suscripción está suspendida o cancelada."""

    pass


class PlanLimitExceeded(Exception):
    """Se alcanzó un límite del plan actual."""

    def __init__(self, message="Plan limit reached", limit_key=None):
        self.limit_key = limit_key
        super().__init__(message)
