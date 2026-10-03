"""ASGI lifespan resources owned by one server event loop."""

import traceback
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from dataclasses import dataclass
from inspect import isasyncgen, iscoroutine
from typing import Any

from asgiref.typing import ASGIReceiveCallable, ASGISendCallable, Scope
from django.core.asgi import get_asgi_application as django_application
from django.core.exceptions import ImproperlyConfigured
from django.dispatch import Signal

from .settings import get_lifespan_factory, resolve_lifespan
from .signals import asgi_shutdown, asgi_startup

type LifespanFactory[T] = Callable[[], AbstractAsyncContextManager[T]]
_UNSET = object()
_STATE_KEY = "aiodrf_asgi_lifespan.state"
__all__ = [
    "LifespanApplication",
    "LifespanFactory",
    "get_asgi_application",
    "get_lifespan_state",
]


@dataclass(slots=True)
class _LifespanState:
    value: object
    active: bool = True

    def invalidate(self, state: dict[str, object]) -> None:
        self.active = False
        # Request scopes shallow-copy this marker. Invalidate access and drop
        # its reference so retained requests do not keep a closed pool alive.
        self.value = None
        if state.get(_STATE_KEY) is self:
            del state[_STATE_KEY]


def get_lifespan_state[T](request: object, expected_type: type[T]) -> T:
    """Return the live, typed resource; never create one on first access.

    ``expected_type`` must support ``isinstance`` (a dataclass is suitable;
    ``TypedDict`` is not). Both Django and DRF requests are accepted.
    """
    # ``state`` is optional in the ASGI specification, and may be ``None``.
    state = ((getattr(request, "scope", None) or {}).get("state") or {}).get(_STATE_KEY)
    if not isinstance(state, _LifespanState) or not state.active:
        raise ImproperlyConfigured(
            "No active lifespan state. Use aiodrf-asgi-lifespan with "
            "a lifespan context manager and a server that propagates scope['state']."
        )
    if not isinstance(state.value, expected_type):
        raise ImproperlyConfigured(
            f"Lifespan state must be {expected_type.__qualname__}, "
            f"not {type(state.value).__qualname__}."
        )
    return state.value


async def _send_signal(signal: Signal, sender: object, scope: Scope) -> None:
    # Robust dispatch waits for every receiver. A first failure must not
    # leave other resource-owning receivers running after lifespan returns.
    responses = await signal.asend_robust(sender=sender, scope=scope)
    for _receiver, result in responses:
        if isinstance(result, Exception):
            raise result


async def _expect_message(receive: ASGIReceiveCallable, phase: str) -> None:
    message = await receive()
    if message["type"] != f"lifespan.{phase}":
        raise RuntimeError(f"Expected lifespan.{phase}, received {message['type']!r}.")


class LifespanApplication:
    """ASGI application answering ``lifespan`` and delegating the rest."""

    def __init__(
        self,
        application: Callable[..., Awaitable[None]],
        *,
        lifespan: LifespanFactory[object] | None = None,
    ) -> None:
        self.application = application
        self.lifespan = resolve_lifespan(lifespan)

    async def __call__(
        self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        if scope["type"] != "lifespan":
            await self.application(scope, receive, send)
            return
        if self.lifespan is not None:
            await self._managed_lifespan(scope, receive, send)
            return
        # Preserve the signal-only protocol for existing applications.
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    await _send_signal(asgi_startup, type(self), scope)
                except Exception:  # noqa: BLE001 -- reported to the server, whatever it is
                    await send(
                        {
                            "type": "lifespan.startup.failed",
                            "message": traceback.format_exc(),
                        }
                    )
                    return
                else:
                    await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                try:
                    await _send_signal(asgi_shutdown, type(self), scope)
                except Exception:  # noqa: BLE001
                    await send(
                        {
                            "type": "lifespan.shutdown.failed",
                            "message": traceback.format_exc(),
                        }
                    )
                else:
                    await send({"type": "lifespan.shutdown.complete"})
                return

    async def _open_lifespan(self, stack: AsyncExitStack, scope: Scope) -> None:
        factory = self.lifespan
        if factory is None:
            raise RuntimeError("No lifespan factory configured.")
        context = factory()
        if not isinstance(context, AbstractAsyncContextManager):
            # A malformed sync factory can return a coroutine/generator.
            # Do not execute it or leak an unawaited-coroutine warning.
            if iscoroutine(context):
                context.close()
            elif isasyncgen(context):
                await context.aclose()
            raise ImproperlyConfigured(
                "LIFESPAN must return an async context manager. "
                "Use @contextlib.asynccontextmanager."
            )
        resource = await stack.enter_async_context(context)
        if resource is None:
            return
        state = scope.get("state")
        if state is None:
            raise ImproperlyConfigured(
                "A lifespan yielding resources requires server support for scope['state']."
            )
        if _STATE_KEY in state:
            raise ImproperlyConfigured(
                "scope['state']['aiodrf_asgi_lifespan.state'] is already in use."
            )
        published = _LifespanState(resource)
        state[_STATE_KEY] = published
        # Remove access before __aexit__ starts closing the resource. All
        # shallow request copies share the same invalidation marker.
        stack.callback(published.invalidate, state)

    async def _managed_lifespan(
        self,
        scope: Scope,
        receive: ASGIReceiveCallable,
        send: Callable[[Any], Awaitable[None]],
    ) -> None:
        phase = "startup"
        stack = AsyncExitStack()
        try:
            try:
                await _expect_message(receive, "startup")
                await self._open_lifespan(stack, scope)
                await _send_signal(asgi_startup, type(self), scope)
                await send({"type": "lifespan.startup.complete"})
                phase = "shutdown"
                await _expect_message(receive, "shutdown")
                await _send_signal(asgi_shutdown, type(self), scope)
            except BaseException as exc:
                try:
                    await stack.__aexit__(type(exc), exc, exc.__traceback__)
                finally:
                    # Cleanup cannot suppress cancellation or interpreter exit.
                    if not isinstance(exc, Exception):
                        raise exc  # noqa: TRY201 -- preserve cancellation if cleanup raised
                # Suppressing an exception inside the user's context must not
                # turn a failed startup/shutdown into a success response.
                raise
            else:
                await stack.aclose()
        except Exception:  # noqa: BLE001 -- the ASGI protocol reports failures
            await send(
                {"type": f"lifespan.{phase}.failed", "message": traceback.format_exc()}
            )
        else:
            await send({"type": "lifespan.shutdown.complete"})


def get_asgi_application(*, lifespan: Any = _UNSET) -> LifespanApplication:
    """Wrap Django; explicit None disables DJANGO_LIFESPAN."""
    application = django_application()
    factory = (
        get_lifespan_factory() if lifespan is _UNSET else resolve_lifespan(lifespan)
    )
    return LifespanApplication(application, lifespan=factory)
