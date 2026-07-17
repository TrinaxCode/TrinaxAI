"""Public process health and resource information."""

from fastapi import APIRouter

from app.services import health_service as runtime

router = APIRouter(tags=["health"])
router.add_api_route("/health", runtime.health, methods=["GET"])
router.add_api_route("/resources", runtime.resources, methods=["GET"])
