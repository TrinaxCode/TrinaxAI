"""Deep-research route."""

from fastapi import APIRouter

from app.services import research_service as runtime

router = APIRouter(tags=["research"])
router.add_api_route("/v1/research", runtime.research, methods=["POST"])
router.add_api_route("/v1/research/preflight", runtime.research_preflight, methods=["POST"])
