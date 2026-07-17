"""Chat attachment services."""

from __future__ import annotations

# ruff: noqa: F405
from .shared_runtime import *  # noqa: F403


def _attachment_paths(attachment_id: str) -> tuple[str, str]:
    if not re.fullmatch(r"[0-9a-f]{32}", attachment_id):
        raise HTTPException(status_code=404, detail="Attachment not found.")
    return (
        os.path.join(CHAT_ATTACHMENTS_DIR, f"{attachment_id}.bin"),
        os.path.join(CHAT_ATTACHMENTS_DIR, f"{attachment_id}.json"),
    )


def _attachment_usage_unlocked() -> tuple[int, int]:
    try:
        entries = os.scandir(CHAT_ATTACHMENTS_DIR)
    except OSError:
        return 0, 0
    total = count = 0
    with entries:
        for entry in entries:
            if not entry.is_file(follow_symlinks=False) or not entry.name.endswith(".bin"):
                continue
            try:
                total += entry.stat(follow_symlinks=False).st_size
                count += 1
            except OSError:
                continue
    return total, count


async def attachment_upload(request: Request, file: UploadFile = File(...)):
    """Store a chat file on the TrinaxAI host for cross-device access."""
    _authorize_system(request)
    enforce_rate_limit(request, bucket="attachment_upload")
    attachment_id = uuid.uuid4().hex
    data_path, metadata_path = _attachment_paths(attachment_id)
    temporary_data_path = f"{data_path}.upload"
    temporary_metadata_path = f"{metadata_path}.tmp"
    os.makedirs(CHAT_ATTACHMENTS_DIR, exist_ok=True)
    size = 0
    try:
        with open(temporary_data_path, "xb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > CHAT_ATTACHMENT_MAX_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Attachment is too large. Limit: {CHAT_ATTACHMENT_MAX_BYTES} bytes.",
                    )
                output.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="Empty attachment.")
        supplied_type = (file.content_type or "application/octet-stream").lower()
        safe_type = supplied_type if supplied_type in _SAFE_INLINE_ATTACHMENT_TYPES else "application/octet-stream"
        metadata = {
            "id": attachment_id,
            "name": os.path.basename(file.filename or "attachment"),
            "size": size,
            "mime_type": safe_type,
            "created_at": time.time(),
        }
        with open(temporary_metadata_path, "x", encoding="utf-8") as stream:
            json.dump(metadata, stream, ensure_ascii=False)

        # Commit both files while holding the quota lock. Uploads are written to
        # an uncounted temporary suffix, so concurrent requests cannot observe
        # partial sizes or all pass the same quota snapshot.
        with state.attachment_lock:
            existing_bytes, existing_files = _attachment_usage_unlocked()
            if existing_files >= CHAT_ATTACHMENTS_MAX_FILES:
                raise HTTPException(status_code=507, detail="Attachment file quota exceeded.")
            if existing_bytes + size > CHAT_ATTACHMENTS_MAX_BYTES:
                raise HTTPException(status_code=507, detail="Attachment storage quota exceeded.")
            os.replace(temporary_data_path, data_path)
            os.replace(temporary_metadata_path, metadata_path)
        return {"ok": True, **metadata, "storage_key": f"server:{attachment_id}"}
    except Exception:
        for path in (data_path, metadata_path, temporary_data_path, temporary_metadata_path):
            try:
                os.remove(path)
            except OSError:
                pass
        raise
    finally:
        await file.close()


async def attachment_get(attachment_id: str, request: Request):
    """Download a previously uploaded chat attachment by its id.

    Descarga un adjunto de chat previamente subido, por su id.
    """
    _authorize_system(request)
    enforce_rate_limit(request, bucket="attachment_download")
    data_path, metadata_path = _attachment_paths(attachment_id)
    try:
        with open(metadata_path, encoding="utf-8") as stream:
            metadata = json.load(stream)
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="Attachment not found.")
    if not os.path.isfile(data_path):
        raise HTTPException(status_code=404, detail="Attachment not found.")
    stored_type = str(metadata.get("mime_type") or "application/octet-stream").lower()
    media_type = stored_type if stored_type in _SAFE_INLINE_ATTACHMENT_TYPES else "application/octet-stream"
    inline = media_type in _SAFE_INLINE_ATTACHMENT_TYPES
    return FileResponse(
        data_path,
        media_type=media_type,
        filename=os.path.basename(str(metadata.get("name") or "attachment")),
        content_disposition_type="inline" if inline else "attachment",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


async def attachment_delete(attachment_id: str, request: Request):
    """Delete a stored chat attachment (data + metadata) from the host.

    Elimina un adjunto de chat almacenado (datos y metadatos) del equipo.
    """
    _authorize_system(request)
    enforce_rate_limit(request, bucket="attachment_delete")
    removed = False
    with state.attachment_lock:
        for path in _attachment_paths(attachment_id):
            try:
                os.remove(path)
                removed = True
            except FileNotFoundError:
                continue
    if not removed:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    return {"ok": True, "deleted": attachment_id}


__all__ = [name for name in globals() if not name.startswith("__")]
