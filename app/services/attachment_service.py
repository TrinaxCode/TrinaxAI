"""Chat attachment services."""

from __future__ import annotations

import mimetypes
import stat

from .runtime_context import (
    _ensure_private_directory,
    _ensure_private_file,
    _open_private_file,
)

# ruff: noqa: F405
from .shared_runtime import (
    _SAFE_ATTACHMENT_TYPES,
    _SAFE_INLINE_ATTACHMENT_TYPES,
    CHAT_ATTACHMENT_MAX_BYTES,
    CHAT_ATTACHMENTS_DIR,
    CHAT_ATTACHMENTS_MAX_BYTES,
    CHAT_ATTACHMENTS_MAX_FILES,
    File,
    FileResponse,
    HTTPException,
    Request,
    UploadFile,
    _authorize_system,
    _client_host,
    _is_local_client,
    enforce_rate_limit,
    json,
    os,
    re,
    state,
    subprocess,
    sys,
    time,
    uuid,
)

_ATTACHMENT_MIME_BY_EXTENSION = {
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odp": "application/vnd.oasis.opendocument.presentation",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".pdf": "application/pdf",
}


def _attachment_name(filename: object) -> str:
    """Return a safe, single filename for Content-Disposition."""
    value = str(filename or "attachment").replace("\\", "/").split("/")[-1]
    value = "".join(character for character in value if ord(character) >= 32 and character not in '"')
    return value[:255] or "attachment"


def _attachment_mime(name: str, supplied_type: object) -> str:
    supplied = str(supplied_type or "").split(";", 1)[0].strip().lower()
    if supplied in _SAFE_ATTACHMENT_TYPES:
        return supplied
    extension = os.path.splitext(name)[1].lower()
    inferred = _ATTACHMENT_MIME_BY_EXTENSION.get(extension) or mimetypes.guess_type(name)[0]
    return inferred if inferred in _SAFE_ATTACHMENT_TYPES else "application/octet-stream"


def _attachment_paths(attachment_id: str) -> tuple[str, str]:
    if not re.fullmatch(r"[0-9a-f]{32}", attachment_id):
        raise HTTPException(status_code=404, detail="Attachment not found.")
    return (
        os.path.join(CHAT_ATTACHMENTS_DIR, f"{attachment_id}.bin"),
        os.path.join(CHAT_ATTACHMENTS_DIR, f"{attachment_id}.json"),
    )


def _is_regular_file(path: str) -> bool:
    try:
        return stat.S_ISREG(os.stat(path, follow_symlinks=False).st_mode)
    except OSError:
        return False


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
    size = 0
    try:
        _ensure_private_directory(CHAT_ATTACHMENTS_DIR)
        with os.fdopen(
            _open_private_file(temporary_data_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL),
            "wb",
        ) as output:
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
        safe_name = _attachment_name(file.filename)
        safe_type = _attachment_mime(safe_name, file.content_type)
        metadata = {
            "id": attachment_id,
            "name": safe_name,
            "size": size,
            "mime_type": safe_type,
            "created_at": time.time(),
        }
        with os.fdopen(
            _open_private_file(temporary_metadata_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL),
            "w",
            encoding="utf-8",
        ) as stream:
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
            _ensure_private_file(data_path)
            _ensure_private_file(metadata_path)
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
    if not _is_regular_file(data_path) or not _is_regular_file(metadata_path):
        raise HTTPException(status_code=404, detail="Attachment not found.")
    _ensure_private_file(data_path)
    _ensure_private_file(metadata_path)
    try:
        with open(metadata_path, encoding="utf-8") as stream:
            metadata = json.load(stream)
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="Attachment not found.") from None
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=404, detail="Attachment not found.")
    name = _attachment_name(metadata.get("name"))
    media_type = _attachment_mime(name, metadata.get("mime_type"))
    inline = media_type in _SAFE_INLINE_ATTACHMENT_TYPES
    return FileResponse(
        data_path,
        media_type=media_type,
        filename=name,
        content_disposition_type="inline" if inline else "attachment",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


async def attachment_open(attachment_id: str, request: Request):
    """Open an uploaded attachment with the host's default application."""
    _authorize_system(request)
    enforce_rate_limit(request, bucket="attachment_open")
    if not _is_local_client(_client_host(request)):
        raise HTTPException(status_code=403, detail="Host application opening is localhost-only.")
    data_path, metadata_path = _attachment_paths(attachment_id)
    if not _is_regular_file(data_path) or not _is_regular_file(metadata_path):
        raise HTTPException(status_code=404, detail="Attachment not found.")
    _ensure_private_file(data_path)
    _ensure_private_file(metadata_path)
    try:
        if sys.platform == "win32":
            os.startfile(data_path)  # type: ignore[attr-defined,no-untyped-call]
        else:
            command = ["open", data_path] if sys.platform == "darwin" else ["xdg-open", data_path]
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(status_code=503, detail="Could not open attachment on the host.") from exc
    return {"ok": True, "opened": attachment_id}


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
