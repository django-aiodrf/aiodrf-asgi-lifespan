from django.http import JsonResponse

from aiodrf_asgi_lifespan.asgi import get_lifespan_state

from .lifecycle import Resources


async def state(request):
    resources = get_lifespan_state(request, Resources)
    return JsonResponse({"pid": resources.pid, "token": resources.token})
