"""Shared PWA application-state routes."""

from fastapi import APIRouter, Depends

from app.security.admin_auth import authorize_system
from app.services import app_state_service as runtime

router = APIRouter(tags=["app-state"], dependencies=[Depends(authorize_system)])
router.add_api_route("/app-state", runtime.app_state_get, methods=["GET"])
router.add_api_route("/app-state", runtime.app_state_put, methods=["PUT"])
router.add_api_route("/app-state", runtime.app_state_delete, methods=["DELETE"])
