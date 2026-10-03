"""Drive a lifespan around a test and yield its ASGI state."""

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from typing import Any

from .asgi import LifespanApplication, LifespanFactory
from .settings import get_lifespan_factory

_UNSET: Any = object()


async def _no_http(scope: Any, receive: Any, send: Any) -> None:
    raise AssertionError("The test lifespan answers lifespan scopes only.")


@contextlib.asynccontextmanager
async def lifespan(
    factory: LifespanFactory[object] | None = _UNSET,
) -> AsyncGenerator[dict[str, Any]]:
    """
    Run the application's lifespan around a block, as an ASGI server would:
    enter ``factory`` (``DJANGO_LIFESPAN`` by default), send the startup
    signal, and on exit the shutdown signal, then close. Yields the lifespan
    state the server would keep; give it to ``AsyncAPIClient(lifespan=...)``
    or ``AsyncAPIRequestFactory(lifespan=...)``. A failed startup or
    shutdown raises ``RuntimeError`` with the application's report.
    """
    if factory is _UNSET:
        factory = get_lifespan_factory()
    application = LifespanApplication(_no_http, lifespan=factory)
    state: dict[str, Any] = {}
    scope = {
        "type": "lifespan",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "state": state,
    }
    incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    outgoing: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    task = asyncio.create_task(application(scope, incoming.get, outgoing.put))  # type: ignore[arg-type]

    async def run(phase: Any) -> None:
        await incoming.put({"type": f"lifespan.{phase}"})
        response = asyncio.create_task(outgoing.get())
        try:
            done, _ = await asyncio.wait(
                (response, task), return_when=asyncio.FIRST_COMPLETED
            )
            if response not in done:
                await task  # Propagate cancellation or an unexpected task failure.
                raise RuntimeError(f"Lifespan ended without a {phase} response.")
            message = response.result()
        finally:
            if not response.done():
                response.cancel()
            await asyncio.gather(response, return_exceptions=True)
        if message["type"] == f"lifespan.{phase}.failed":
            await task
            raise RuntimeError(f"Lifespan {phase} failed:\n{message['message']}")

    try:
        await run("startup")
    except BaseException:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        raise
    try:
        yield state
    finally:
        try:
            await run("shutdown")
            await task
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
