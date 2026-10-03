# Security policy

## Supported versions

Security fixes are made for the latest release of aiodrf-asgi-lifespan. Upgrade to it
before reporting an issue, if you can.

## Reporting a vulnerability

Report a suspected vulnerability privately through GitHub's private
vulnerability reporting:
[open a report](https://github.com/django-aiodrf/aiodrf-asgi-lifespan/security/advisories/new)
on the repository's Security tab. Do not open a public issue or pull request
for it.

Include the affected version, the Django and Python versions, the settings
involved, and the steps to reproduce. Do not include credentials, personal
data or production data.

You will receive an acknowledgement, and the advisory will be published with
the fixed release once a fix is available.

## Scope

aiodrf-asgi-lifespan runs a project's lifespan context in each ASGI
server lifespan and publishes its resources to requests. A report is in
scope when a request can reach a resource of another lifespan, or one
that was closed, or when startup or shutdown reports success after a
failure.
