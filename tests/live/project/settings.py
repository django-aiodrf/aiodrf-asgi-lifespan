"""A project without a database, served by real ASGI servers."""

SECRET_KEY = "live-server-tests"
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1"]
INSTALLED_APPS = []
MIDDLEWARE = []
ROOT_URLCONF = "project.urls"
USE_TZ = True
DJANGO_LIFESPAN = "project.lifecycle.resources"
