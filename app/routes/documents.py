"""Document-to-text extraction route."""

from fastapi import APIRouter, Depends

from app.schemas import DocumentExtractResponse
from app.security.admin_auth import require_lan_or_scope
from app.services import document_service as runtime

# Temporary extraction returns text from the caller's own upload and does not
# read or persist TrinaxAI private data, so it is available to LAN/VPN peers in
# the same way as basic image analysis. Public-network callers still need a
# valid chat credential.
router = APIRouter(tags=["documents"], dependencies=[Depends(require_lan_or_scope("chat"))])
router.add_api_route(
    "/documents/extract",
    runtime.document_extract,
    methods=["POST"],
    response_model=DocumentExtractResponse,
)
