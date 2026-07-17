"""Privileged service lifecycle and indexing routes."""

from fastapi import APIRouter

from app.services import system_service as runtime

router = APIRouter(tags=["system"])
router.add_api_route("/system/shutdown", runtime.system_shutdown, methods=["POST"])
router.add_api_route("/system/startup", runtime.system_startup, methods=["POST"])
router.add_api_route("/system/stop-all", runtime.system_stop_all, methods=["POST"])
router.add_api_route("/system/reload", runtime.system_reload, methods=["POST"])
router.add_api_route("/system/index-upload", runtime.system_index_upload, methods=["POST"])
router.add_api_route("/system/index-imports", runtime.system_delete_index_import, methods=["DELETE"])
router.add_api_route("/system/index-jobs/{job_id}", runtime.system_index_job, methods=["GET"])
router.add_api_route(
    "/system/index-jobs/{job_id}/cancel",
    runtime.system_cancel_index_job,
    methods=["POST"],
)
router.add_api_route(
    "/system/index-jobs/{job_id}/retry",
    runtime.system_retry_index_job,
    methods=["POST"],
)
router.add_api_route("/system/self-test", runtime.system_self_test, methods=["POST"])
