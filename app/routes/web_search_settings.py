"""Administrative web-search settings routes."""

from fastapi import APIRouter

from app.services import web_search_settings_service as runtime

router = APIRouter(prefix="/v1/settings/web-search", tags=["settings"])
router.add_api_route("", runtime.get_web_search_settings, methods=["GET"])
router.add_api_route("", runtime.update_web_search_settings, methods=["PUT"])
router.add_api_route("", runtime.reset_web_search_settings, methods=["DELETE"])
router.add_api_route("/test", runtime.test_web_search_connection, methods=["POST"])
router.add_api_route("/credentials/{provider}", runtime.delete_web_search_credential, methods=["DELETE"])
