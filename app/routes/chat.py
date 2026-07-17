"""OpenAI-compatible chat endpoint."""

from fastapi import APIRouter, Depends

from app.security.admin_auth import require_scope
from app.services import rag_service as runtime

router = APIRouter(tags=["chat"], dependencies=[Depends(require_scope("chat"))])
router.add_api_route("/v1/chat/completions", runtime.chat, methods=["POST"], name="chat")
