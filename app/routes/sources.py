"""Indexed source browsing and deletion routes."""

from fastapi import APIRouter

from app.services import sources_service as runtime

router = APIRouter(tags=["sources"])
router.add_api_route("/v1/sources", runtime.sources_list, methods=["GET"])
router.add_api_route(
    "/v1/sources/{collection}/{file:path}/chunks",
    runtime.sources_chunks,
    methods=["GET"],
)
router.add_api_route(
    "/v1/sources/{collection}/{file:path}",
    runtime.sources_delete,
    methods=["DELETE"],
)
router.add_api_route(
    "/v1/sources/{collection}",
    runtime.sources_delete_collection,
    methods=["DELETE"],
)
