"""Chat attachment upload, download and deletion."""

from fastapi import APIRouter, Depends

from app.security.admin_auth import authorize_system
from app.services import attachment_service as runtime

router = APIRouter(tags=["attachments"], dependencies=[Depends(authorize_system)])
router.add_api_route("/attachments", runtime.attachment_upload, methods=["POST"])
router.add_api_route("/attachments/{attachment_id}", runtime.attachment_get, methods=["GET"])
router.add_api_route("/attachments/{attachment_id}", runtime.attachment_delete, methods=["DELETE"])
