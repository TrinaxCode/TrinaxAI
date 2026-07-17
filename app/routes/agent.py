"""Agentic assistant routes (file/shell tool-use over a workspace)."""

from fastapi import APIRouter, Depends

from app.security.admin_auth import authorize_system
from app.services import agent_service as runtime

router = APIRouter(tags=["agent"], dependencies=[Depends(authorize_system)])
router.add_api_route("/v1/agent", runtime.agent, methods=["POST"])
router.add_api_route("/v1/agent/approve", runtime.agent_approve, methods=["POST"])
router.add_api_route("/v1/agent/browse", runtime.agent_browse, methods=["GET"])
