# The live tests start ASGI servers as processes. A plain `pytest` skips the
# directory; `nox -s servers` runs it by naming it: `pytest tests/live`.
collect_ignore = ["live"]
