"""User memory CRUD and summarization routes."""

from fastapi import APIRouter

from app.services import memory_service as runtime

router = APIRouter(tags=["memory"])
router.add_api_route("/v1/memory", runtime.memory_list, methods=["GET"])
router.add_api_route("/v1/memory", runtime.memory_create, methods=["POST"])
router.add_api_route("/v1/memory/{memory_id}", runtime.memory_update, methods=["PATCH"])
router.add_api_route("/v1/memory/{memory_id}", runtime.memory_delete, methods=["DELETE"])
router.add_api_route("/v1/memory/context", runtime.memory_context, methods=["POST"])
router.add_api_route("/v1/memory/refresh", runtime.memory_refresh, methods=["POST"])
router.add_api_route("/v1/memory/summary", runtime.memory_summary, methods=["GET"])
