"""Annotations of the public API, checked by mypy and never run.

pytest collects ``test_*.py`` only, so it does not import this module.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import assert_type

from aiodrf_asgi_lifespan.asgi import (
    LifespanApplication,
    LifespanFactory,
    get_asgi_application,
)
from aiodrf_asgi_lifespan.settings import get_lifespan_factory, resolve_lifespan


@asynccontextmanager
async def resources() -> AsyncIterator[str]:
    yield "resource"


def check_settings() -> None:
    assert_type(get_lifespan_factory(), LifespanFactory[object] | None)
    assert_type(resolve_lifespan("project.resources"), LifespanFactory[object] | None)


def check_get_asgi_application() -> None:
    assert_type(get_asgi_application(), LifespanApplication)
    get_asgi_application(lifespan="project.resources")
    get_asgi_application(lifespan=resources)
    get_asgi_application(lifespan=None)
    get_asgi_application(lifespan=1)  # type: ignore[arg-type]
