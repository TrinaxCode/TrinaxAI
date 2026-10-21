"""Shared error taxonomy and safe, client-facing error metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    INTERNET_UNAVAILABLE = "internet_unavailable"
    EXTERNAL_SERVICE_UNAVAILABLE = "external_service_unavailable"
    AI_MODEL_UNAVAILABLE = "ai_model_unavailable"
    MODEL_LOADING_FAILED = "model_loading_failed"
    TOOL_TIMEOUT = "tool_timeout"
    PERMISSION_DENIED = "permission_denied"
    AUTHENTICATION_FAILED = "authentication_failed"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    MEMORY_LIMIT_REACHED = "memory_limit_reached"
    GPU_UNAVAILABLE = "gpu_unavailable"
    FILE_NOT_FOUND = "file_not_found"
    DOCUMENT_UNREADABLE = "document_unreadable"
    INVALID_INPUT = "invalid_input"
    UNSUPPORTED_FORMAT = "unsupported_format"
    NETWORK_TIMEOUT = "network_timeout"
    INTERNAL_SERVER_ERROR = "internal_server_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass(frozen=True)
class ErrorDefinition:
    code: str
    message: str
    recovery: str
    message_es: str
    recovery_es: str
    developer_log: str
    retryable: bool


_D = ErrorDefinition
ERROR_DEFINITIONS: dict[ErrorCategory, ErrorDefinition] = {
    ErrorCategory.INTERNET_UNAVAILABLE: _D(
        "ERR_INTERNET_UNAVAILABLE",
        "The internet connection is unavailable.",
        "Check the network connection and try again.",
        "La conexión a Internet no está disponible.",
        "Verifica la conexión de red e inténtalo de nuevo.",
        "internet connectivity unavailable",
        True,
    ),
    ErrorCategory.EXTERNAL_SERVICE_UNAVAILABLE: _D(
        "ERR_EXTERNAL_SERVICE_UNAVAILABLE",
        "An external service is unavailable.",
        "Check the service status and try again shortly.",
        "Un servicio externo no está disponible.",
        "Verifica el estado del servicio e inténtalo de nuevo en unos momentos.",
        "external dependency unavailable",
        True,
    ),
    ErrorCategory.AI_MODEL_UNAVAILABLE: _D(
        "ERR_AI_MODEL_UNAVAILABLE",
        "The selected AI model is unavailable.",
        "Check that the model is installed and the AI service is running.",
        "El modelo de IA seleccionado no está disponible.",
        "Verifica que el modelo esté instalado y que el servicio de IA esté encendido.",
        "AI model unavailable",
        False,
    ),
    ErrorCategory.MODEL_LOADING_FAILED: _D(
        "ERR_MODEL_LOADING_FAILED",
        "The AI model could not be loaded.",
        "Free system memory or select a smaller model, then try again.",
        "No se pudo cargar el modelo de IA.",
        "Libera memoria o selecciona un modelo más pequeño e inténtalo de nuevo.",
        "AI model load failed",
        True,
    ),
    ErrorCategory.TOOL_TIMEOUT: _D(
        "ERR_TOOL_TIMEOUT",
        "The operation took too long to finish.",
        "Try again with a smaller request or a narrower scope.",
        "La operación tardó demasiado en terminar.",
        "Inténtalo de nuevo con una solicitud más pequeña o específica.",
        "tool execution timeout",
        True,
    ),
    ErrorCategory.PERMISSION_DENIED: _D(
        "ERR_PERMISSION_DENIED",
        "You do not have permission to perform this action.",
        "Request access or use an authorized device.",
        "No tienes permiso para realizar esta acción.",
        "Solicita acceso o usa un dispositivo autorizado.",
        "authorization denied",
        False,
    ),
    ErrorCategory.AUTHENTICATION_FAILED: _D(
        "ERR_AUTHENTICATION_FAILED",
        "Authentication failed.",
        "Sign in again or provide valid credentials.",
        "La autenticación falló.",
        "Inicia sesión de nuevo o proporciona credenciales válidas.",
        "authentication failed",
        False,
    ),
    ErrorCategory.RESOURCE_EXHAUSTED: _D(
        "ERR_RESOURCE_EXHAUSTED",
        "The service has reached a temporary resource limit.",
        "Wait a moment and try again.",
        "El servicio alcanzó un límite temporal de recursos.",
        "Espera un momento e inténtalo de nuevo.",
        "service resource limit reached",
        True,
    ),
    ErrorCategory.MEMORY_LIMIT_REACHED: _D(
        "ERR_MEMORY_LIMIT_REACHED",
        "The operation needs more memory than is currently available.",
        "Use a smaller file or model, or free system memory.",
        "La operación necesita más memoria de la disponible.",
        "Usa un archivo o modelo más pequeño, o libera memoria del sistema.",
        "memory limit reached",
        False,
    ),
    ErrorCategory.GPU_UNAVAILABLE: _D(
        "ERR_GPU_UNAVAILABLE",
        "The requested GPU is unavailable.",
        "Switch to CPU mode or make the GPU available, then try again.",
        "La GPU solicitada no está disponible.",
        "Cambia al modo CPU o habilita la GPU e inténtalo de nuevo.",
        "GPU unavailable",
        False,
    ),
    ErrorCategory.FILE_NOT_FOUND: _D(
        "ERR_FILE_NOT_FOUND",
        "The requested file was not found.",
        "Check the file location and try again.",
        "No se encontró el archivo solicitado.",
        "Verifica la ubicación del archivo e inténtalo de nuevo.",
        "file or resource not found",
        False,
    ),
    ErrorCategory.DOCUMENT_UNREADABLE: _D(
        "ERR_DOCUMENT_UNREADABLE",
        "The document could not be read.",
        "Check that the document is not damaged and try another copy.",
        "No se pudo leer el documento.",
        "Verifica que el documento no esté dañado e inténtalo con otra copia.",
        "document parsing failed",
        False,
    ),
    ErrorCategory.INVALID_INPUT: _D(
        "ERR_INVALID_INPUT",
        "The request contains invalid input.",
        "Check the fields and try again.",
        "La solicitud contiene datos inválidos.",
        "Verifica los campos e inténtalo de nuevo.",
        "input validation failed",
        False,
    ),
    ErrorCategory.UNSUPPORTED_FORMAT: _D(
        "ERR_UNSUPPORTED_FORMAT",
        "This file or format is not supported.",
        "Use a supported format and try again.",
        "Este archivo o formato no es compatible.",
        "Usa un formato compatible e inténtalo de nuevo.",
        "unsupported format",
        False,
    ),
    ErrorCategory.NETWORK_TIMEOUT: _D(
        "ERR_NETWORK_TIMEOUT",
        "The network request timed out.",
        "Check the connection and try again.",
        "La solicitud de red agotó el tiempo de espera.",
        "Verifica la conexión e inténtalo de nuevo.",
        "network request timeout",
        True,
    ),
    ErrorCategory.INTERNAL_SERVER_ERROR: _D(
        "ERR_INTERNAL_SERVER_ERROR",
        "TrinaxAI could not complete the request.",
        "Try again. If the problem continues, check the server logs.",
        "TrinaxAI no pudo completar la solicitud.",
        "Inténtalo de nuevo. Si continúa, revisa los registros del servidor.",
        "unhandled internal server failure",
        True,
    ),
    ErrorCategory.UNKNOWN_ERROR: _D(
        "ERR_UNKNOWN_ERROR",
        "Something unexpected happened.",
        "Try again. If the problem continues, contact an administrator.",
        "Ocurrió un error inesperado.",
        "Inténtalo de nuevo. Si continúa, contacta a un administrador.",
        "unclassified failure",
        False,
    ),
}


@dataclass(frozen=True)
class ErrorInfo:
    category: ErrorCategory
    definition: ErrorDefinition
    exception_type: str = ""
    legacy_code: str | None = None

    @property
    def code(self) -> str:
        return self.definition.code

    @property
    def retryable(self) -> bool:
        return self.definition.retryable

    def to_client_dict(self, *, spanish: bool = False) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "code": self.code,
            "message": self.definition.message_es if spanish else self.definition.message,
            "recovery": self.definition.recovery_es if spanish else self.definition.recovery,
            "retryable": self.retryable,
        }


class TrinaxError(RuntimeError):
    """An optional typed error for code that knows its failure category."""

    def __init__(self, category: ErrorCategory, message: str = "", *, legacy_code: str | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.legacy_code = legacy_code


def error_for(category: ErrorCategory, *, exception_type: str = "", legacy_code: str | None = None) -> ErrorInfo:
    return ErrorInfo(category, ERROR_DEFINITIONS[category], exception_type, legacy_code)


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(str(value.get(key, "")) for key in ("code", "message", "detail", "provider", "field"))
    return str(value or "")


def _category_from_hint(hint: str, status_code: int | None) -> ErrorCategory | None:
    lowered = hint.casefold()
    if any(token in lowered for token in ("gpu", "cuda", "rocm", "no gpu")):
        return ErrorCategory.GPU_UNAVAILABLE
    if any(
        token in lowered for token in ("model load", "load model", "runner failed", "llama runner", "unexpected eof")
    ):
        return ErrorCategory.MODEL_LOADING_FAILED
    if any(
        token in lowered
        for token in ("model unavailable", "model not found", "ollama_unavailable", "ollama is not running")
    ):
        return ErrorCategory.AI_MODEL_UNAVAILABLE
    if any(token in lowered for token in ("tool timeout", "agent timed out", "agent stalled", "execution timed out")):
        return ErrorCategory.TOOL_TIMEOUT
    if any(
        token in lowered
        for token in ("unsupported", "not supported", "requires pypdf", "requires docx", "requires python-pptx")
    ):
        return ErrorCategory.UNSUPPORTED_FORMAT
    if any(
        token in lowered
        for token in ("cannot extract", "could not extract", "document unreadable", "no readable text", "parse failed")
    ):
        return ErrorCategory.DOCUMENT_UNREADABLE
    if any(token in lowered for token in ("permission", "forbidden", "access denied", "unauthorized action")):
        return ErrorCategory.PERMISSION_DENIED
    if any(
        token in lowered for token in ("authentication", "invalid token", "invalid credential", "credential does not")
    ):
        return ErrorCategory.AUTHENTICATION_FAILED
    if any(token in lowered for token in ("memory", "out of memory", "ram", "vram")):
        return ErrorCategory.MEMORY_LIMIT_REACHED
    if any(
        token in lowered for token in ("quota", "rate limit", "too many requests", "resource limit", "storage is full")
    ):
        return ErrorCategory.RESOURCE_EXHAUSTED
    if any(
        token in lowered for token in ("file not found", "attachment not found", "does not exist", "unknown device")
    ):
        return ErrorCategory.FILE_NOT_FOUND
    if "collection" in lowered and any(token in lowered for token in ("not found", "empty", "not initialized")):
        return ErrorCategory.FILE_NOT_FOUND
    if any(token in lowered for token in ("timeout", "timed out", "deadline exceeded")):
        return ErrorCategory.NETWORK_TIMEOUT
    if any(token in lowered for token in ("invalid input", "validation", "must be", "required", "invalid url")):
        return ErrorCategory.INVALID_INPUT
    if status_code == 0:
        return ErrorCategory.INTERNET_UNAVAILABLE
    if status_code in {401}:
        return ErrorCategory.AUTHENTICATION_FAILED
    if status_code in {403}:
        return ErrorCategory.PERMISSION_DENIED
    if status_code in {408, 504}:
        return ErrorCategory.NETWORK_TIMEOUT
    if status_code in {413}:
        return ErrorCategory.MEMORY_LIMIT_REACHED
    if status_code in {404}:
        return ErrorCategory.FILE_NOT_FOUND
    if status_code in {415, 501}:
        return ErrorCategory.UNSUPPORTED_FORMAT
    if status_code in {429, 507}:
        return ErrorCategory.RESOURCE_EXHAUSTED
    if status_code in {422, 400}:
        return ErrorCategory.INVALID_INPUT
    if status_code in {502, 503}:
        return ErrorCategory.EXTERNAL_SERVICE_UNAVAILABLE
    if status_code is not None and status_code >= 500:
        return ErrorCategory.INTERNAL_SERVER_ERROR
    return None


def classify_error(
    exc: BaseException | None = None,
    *,
    status_code: int | None = None,
    hint: Any = "",
    category: ErrorCategory | None = None,
) -> ErrorInfo:
    """Classify an exception without exposing its text to clients."""
    if isinstance(exc, TrinaxError):
        return error_for(exc.category, exception_type=type(exc).__name__, legacy_code=exc.legacy_code)
    exception_type = type(exc).__name__ if exc is not None else ""
    hint_text = f"{_text(hint)} {_text(exc)}".strip()
    selected = category or _category_from_hint(hint_text, status_code)
    if selected is None and exc is not None:
        if isinstance(exc, MemoryError):
            selected = ErrorCategory.MEMORY_LIMIT_REACHED
        elif isinstance(exc, PermissionError):
            selected = ErrorCategory.PERMISSION_DENIED
        elif isinstance(exc, FileNotFoundError):
            selected = ErrorCategory.FILE_NOT_FOUND
        elif isinstance(exc, TimeoutError) or exception_type in {"TimeoutException", "ReadTimeout", "ConnectTimeout"}:
            selected = ErrorCategory.NETWORK_TIMEOUT
        elif isinstance(exc, ConnectionError) or exception_type in {"ConnectError", "NetworkError"}:
            selected = ErrorCategory.INTERNET_UNAVAILABLE
        elif isinstance(exc, (ValueError, TypeError)):
            selected = ErrorCategory.INVALID_INPUT
    return error_for(selected or ErrorCategory.UNKNOWN_ERROR, exception_type=exception_type)


__all__ = [
    "ERROR_DEFINITIONS",
    "ErrorCategory",
    "ErrorDefinition",
    "ErrorInfo",
    "TrinaxError",
    "classify_error",
    "error_for",
]
