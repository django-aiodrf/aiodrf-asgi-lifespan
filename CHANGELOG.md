# Changelog

All notable changes to this project are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project uses [Semantic Versioning](https://semver.org/).

## [0.1.1] - 2026-10-03

### Added

- Tests against real ASGI servers: Uvicorn, Granian and Hypercorn run a
  Django project as processes in the `servers` nox session and CI job.
- README: the order in which Django runs `asgi_startup` and `asgi_shutdown`
  receivers on each supported Django version, how failing receivers are
  reported, and the tested servers. Daphne 4.2.3 is listed as unsupported:
  it does not implement the lifespan protocol.

### Changed

- Annotations: `resolve_lifespan()` and `get_lifespan_factory()` return
  `LifespanFactory[object] | None`, and the `lifespan` argument of
  `get_asgi_application()` is typed as `str | LifespanFactory[object] |
  None`. Runtime behaviour is unchanged.

## [0.1.0] - 2026-10-03

The first release, extracted from django-aiodrf 0.0.2 so that projects that
do not use Django REST framework can use it.

### Added

- `get_asgi_application()` and `LifespanApplication`: an async context
  manager named by the `DJANGO_LIFESPAN` setting, or given as `lifespan=`,
  is entered for each ASGI server lifespan, and its resource is published in
  the lifespan state.
- `get_lifespan_state(request, expected_type)`: the resource of the request's
  lifespan, checked for its type and for an open context.
- `asgi_startup` and `asgi_shutdown` signals, sent with robust async
  dispatch; a failure in a receiver is reported to the server.
- `testing.lifespan()`: runs startup and shutdown around a test block and
  yields the lifespan state for an ASGI test client.
