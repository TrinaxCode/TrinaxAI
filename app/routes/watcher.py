"""Filesystem watcher lifecycle routes."""

from fastapi import APIRouter

from app.services import watcher_service as runtime

router = APIRouter(tags=["watcher"])
router.add_api_route("/v1/watch/start", runtime.watch_start, methods=["POST"])
router.add_api_route("/v1/watch/stop", runtime.watch_stop, methods=["POST"])
router.add_api_route("/v1/watch/status", runtime.watch_status, methods=["GET"])
