"""Public process health and resource information."""

from fastapi import APIRouter, Request

from app.services import health_service as runtime

router = APIRouter(tags=["health"])


async def health(request: Request):
    return await runtime.health(request)


async def ready(request: Request):
    return await runtime.ready(request)


async def resources(request: Request):
    return await runtime.resources(request)


router.add_api_route("/health", health, methods=["GET"])
router.add_api_route("/ready", ready, methods=["GET"])
router.add_api_route("/resources", resources, methods=["GET"])
