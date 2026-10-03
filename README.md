# aiodrf-asgi-lifespan

ASGI lifespan contexts and typed resource access for Django. It runs an async
context manager for each server lifespan and gives requests its resource. It
requires Python 3.12+ and Django 5.2+, and depends on neither Django REST
framework nor django-aiodrf.

```console
pip install aiodrf-asgi-lifespan
```

## Usage

Write the resources as an async context manager:

```python
# project/lifecycle.py
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass
class Resources:
    label: str


@asynccontextmanager
async def resources():
    # Open async clients here, and close them after the yield, with their
    # own context managers or a contextlib.AsyncExitStack.
    yield Resources(label="worker")
```

Name it in the `DJANGO_LIFESPAN` setting:

```python
# settings.py
DJANGO_LIFESPAN = "project.lifecycle.resources"
```

and serve the application this package builds:

```python
# project/asgi.py
import os

from aiodrf_asgi_lifespan.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
application = get_asgi_application()
```

The ASGI server must support the lifespan protocol and `scope["state"]`. Each
server process, and each event loop, enters its own context. Requests receive
a shallow copy of the server's state, so the resources themselves are shared
within the lifespan.

A view reads the resource with its type:

```python
from django.http import JsonResponse

from aiodrf_asgi_lifespan.asgi import get_lifespan_state
from project.lifecycle import Resources


async def status(request):
    resources = get_lifespan_state(request, Resources)
    return JsonResponse({"label": resources.label})
```

`get_lifespan_state()` checks the resource's type and that its context is
still open: a request kept beyond shutdown cannot reach a closed resource.
It accepts Django and DRF requests.

## Other entry points

- `get_asgi_application(lifespan=factory)` uses `factory` instead of the
  setting; `lifespan=None` runs no resource context.
- `LifespanApplication(application, lifespan=factory)` wraps any other ASGI
  application without building Django's handler.
- `aiodrf_asgi_lifespan.signals.asgi_startup` and `asgi_shutdown` are sent
  with Django's robust async dispatch: startup receivers run after the
  context is entered, shutdown receivers before it is closed. A failure in
  either is reported to the server. The signals work without a resource
  context too.

## Testing

`aiodrf_asgi_lifespan.testing.lifespan()` runs startup and shutdown around a
block and yields the lifespan state:

```python
from aiodrf_asgi_lifespan.testing import lifespan


async def test_status():
    async with lifespan() as state:
        ...  # give `state` to an ASGI test client
```

With django-aiodrf, pass it to `aiodrf.test.AsyncAPIClient(lifespan=state)`.

## With django-aiodrf

Install django-aiodrf's `lifespan` extra. When `AIODRF["REQUEST_THREADS"]` is
set, keep `aiodrf.asgi.get_asgi_application()`: it adds request thread reuse
around this package's lifespan.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
