# Cómo instalar django-tenant-core en tus proyectos

El paquete es privado, así que no está en PyPI. Hay dos formas de instalarlo.

---

## Opción A — Desde un release (recomendado para producción)

Cada vez que se sube un tag `vX.X.X`, el CI genera un `.whl` adjunto al release.

```bash
# En requirements.txt del proyecto
https://github.com/Escanor07/django-tenant-core/releases/download/v0.1.0/django_tenant_core-0.1.0-py3-none-any.whl
```

```bash
pip install -r requirements.txt
```

> Para que pip pueda acceder al repo privado necesitas un token de GitHub con scope `repo`.
> En CI/CD agrega el token como secret y úsalo así:
> ```
> pip install https://${GH_TOKEN}@raw.githubusercontent.com/Escanor07/...
> ```

---

## Opción B — Desde la rama main (desarrollo activo)

```bash
# requirements.txt
git+https://github.com/Escanor07/django-tenant-core.git@main#egg=django-tenant-core

# o una rama específica
git+https://github.com/Escanor07/django-tenant-core.git@develop#egg=django-tenant-core
```

Para que funcione en máquinas con SSH configurado:
```bash
git+ssh://git@github.com/Escanor07/django-tenant-core.git@main#egg=django-tenant-core
```

---

## Opción C — Instalación local durante desarrollo del core

Si estás modificando el core y un proyecto al mismo tiempo:

```bash
# Clona el core junto al proyecto
git clone git@github.com:Escanor07/django-tenant-core.git

# En el proyecto, instala en modo editable
pip install -e ../django-tenant-core

# Ahora los cambios en el core se reflejan inmediatamente sin reinstalar
```

---

## Verificar la instalación

```python
import tenant_core
# No debe lanzar error

from tenant_core.models import Tenant, TenantAwareModel
from tenant_core.middleware import TenantMiddleware
from tenant_core.context import get_current_tenant
```

---

## Cómo publicar una nueva versión

1. Haz tus cambios en una rama `feature/` o `fix/`
2. Actualiza `CHANGELOG.md` con los cambios
3. Actualiza la versión en `pyproject.toml`
4. Abre un PR → mergealo a `main`
5. Crea el tag desde `main`:

```bash
git checkout main
git pull
git tag v0.2.0
git push origin v0.2.0
```

El CI automáticamente construye el paquete y crea el GitHub Release con el `.whl` adjunto.
