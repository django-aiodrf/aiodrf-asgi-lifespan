"""Check an installed aiodrf-asgi-lifespan wheel without its optional extras.

Every module imports with Django alone, except the modules of optional
drivers, which need their extras. The wheel carries the type marker.
"""

import importlib
import importlib.resources
import pkgutil

import django
from django.conf import settings

settings.configure()
django.setup()

import aiodrf_asgi_lifespan  # noqa: E402

OPTIONAL = ()
modules = sorted(
    info.name
    for info in pkgutil.walk_packages(
        aiodrf_asgi_lifespan.__path__, "aiodrf_asgi_lifespan."
    )
)
for name in modules:
    try:
        importlib.import_module(name)
    except ImportError as exc:
        if name not in OPTIONAL:
            raise
        print(f"{name}: needs its extra ({exc})")

assert (
    importlib.resources.files("aiodrf_asgi_lifespan").joinpath("py.typed").is_file()
), "py.typed is missing"
print(f"{len(modules)} modules checked")
