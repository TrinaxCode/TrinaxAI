"""Local usage statistics routes."""

from fastapi import APIRouter

from app.services import usage_service as runtime

router = APIRouter(tags=["stats"])
router.add_api_route("/v1/usage", runtime.usage_record, methods=["POST"])
router.add_api_route("/v1/stats", runtime.usage_stats, methods=["GET"])
