"""The protocol test helper must observe cancellation of its application task."""

import asyncio
from contextlib import asynccontextmanager

import pytest

from aiodrf_asgi_lifespan.testing import lifespan


@pytest.mark.parametrize("phase", ["startup", "shutdown"])
async def test_cancelled_factory_does_not_leave_helper_waiting_for_a_message(phase):
    @asynccontextmanager
    async def factory():
        if phase == "startup":
            raise asyncio.CancelledError
        yield None
        raise asyncio.CancelledError

    async def run():
        async with lifespan(factory):
            pass

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(run(), 1)
