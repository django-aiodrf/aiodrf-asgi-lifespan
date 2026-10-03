"""ASGI startup/shutdown signals with sender and lifespan scope."""

from django.dispatch import Signal

__all__ = ["asgi_startup", "asgi_shutdown"]
asgi_startup = Signal()
asgi_shutdown = Signal()
