"""Knowledge collection CRUD routes."""

from fastapi import APIRouter

from app.services import collection_service as runtime

router = APIRouter(tags=["collections"])
router.add_api_route("/collections", runtime.collections_get, methods=["GET"])
router.add_api_route("/collections", runtime.collections_create, methods=["POST"])
router.add_api_route("/collections/{collection_id}", runtime.collections_update, methods=["PATCH"])
router.add_api_route("/collections/{collection_id}", runtime.collections_delete, methods=["DELETE"])
