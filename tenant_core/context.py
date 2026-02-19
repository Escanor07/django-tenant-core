# tenant_core/context.py
import threading

_thread_locals = threading.local()


def set_current_tenant(tenant):
    _thread_locals.tenant = tenant


def get_current_tenant():
    return getattr(_thread_locals, 'tenant', None)


def clear_current_tenant():
    _thread_locals.tenant = None
