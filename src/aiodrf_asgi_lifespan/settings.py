"""Resolve the lifespan factory without opening resources or caching settings."""

from inspect import isasyncgenfunction, iscoroutinefunction
from typing import TYPE_CHECKING, cast

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

if TYPE_CHECKING:
    # asgi.py imports this module; a runtime import would be circular.
    from .asgi import LifespanFactory


def resolve_lifespan(value: object) -> "LifespanFactory[object] | None":
    """Validate a callable or import path; never call the factory here."""
    if isinstance(value, str):
        try:
            value = import_string(value)
        except ImportError as exc:
            raise ImportError(f"DJANGO_LIFESPAN: {exc}") from exc
        if not callable(value):
            raise ImproperlyConfigured("DJANGO_LIFESPAN must resolve to a callable.")
    if value is None:
        return None
    if not callable(value):
        raise ImproperlyConfigured(
            "DJANGO_LIFESPAN must be None, a dotted path or a callable."
        )
    if any(
        check(candidate)
        for check in (iscoroutinefunction, isasyncgenfunction)
        for candidate in (value, value.__call__)
    ):
        raise ImproperlyConfigured(
            "DJANGO_LIFESPAN must return an async context manager; "
            "decorate an async generator with @contextlib.asynccontextmanager."
        )
    return cast("LifespanFactory[object]", value)


def get_lifespan_factory() -> "LifespanFactory[object] | None":
    """Read DJANGO_LIFESPAN at application or command construction."""
    return resolve_lifespan(getattr(settings, "DJANGO_LIFESPAN", None))
