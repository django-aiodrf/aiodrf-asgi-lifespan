"""Write each lifespan event to the file named by ``LIFESPAN_LOG``."""

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import uuid4

from django.dispatch import receiver

from aiodrf_asgi_lifespan.signals import asgi_shutdown, asgi_startup


@dataclass
class Resources:
    pid: int
    token: str


def record(event):
    # One short append per line, so that worker processes do not interleave.
    with open(os.environ["LIFESPAN_LOG"], "a") as log:
        log.write(f"{event}\n")


@asynccontextmanager
async def resources():
    if os.environ.get("LIFESPAN_FAIL") == "1":
        raise RuntimeError("startup failed on purpose")
    record(f"opened {os.getpid()}")
    try:
        yield Resources(pid=os.getpid(), token=uuid4().hex)
    finally:
        record(f"closed {os.getpid()}")


# DJANGO_LIFESPAN imports this module when the application is built, before
# the server starts the lifespan, so the receivers are connected in time.
@receiver(asgi_startup)
def sync_startup(sender, **kwargs):
    record("signal startup")


@receiver(asgi_startup)
async def async_startup(sender, **kwargs):
    record("signal startup")


@receiver(asgi_shutdown)
def sync_shutdown(sender, **kwargs):
    record("signal shutdown")


@receiver(asgi_shutdown)
async def async_shutdown(sender, **kwargs):
    record("signal shutdown")
