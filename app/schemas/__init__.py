"""Pydantic models for TrinaxAI API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[dict] = Field(min_length=1, max_length=100)
    stream: bool = False
    collections: list[str] | None = Field(default=None, max_length=50)
    keep_alive: str | int | None = None
    aggressive_quant: bool | None = None

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages: list[dict]) -> list[dict]:
        total_chars = 0
        has_user = False
        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("Each message must be an object.")
            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "user", "assistant"}:
                raise ValueError("Message role must be system, user, or assistant.")
            if not isinstance(content, str):
                raise ValueError("Message content must be text.")
            if len(content) > 100_000:
                raise ValueError("A single message is too large (maximum 100,000 characters).")
            has_user = has_user or role == "user"
            total_chars += len(content)
        if not has_user:
            raise ValueError("At least one user message is required.")
        if total_chars > 200_000:
            raise ValueError("Conversation is too large (maximum 200,000 characters).")
        return messages


class CollectionCreateRequest(BaseModel):
    name: str


class CollectionUpdateRequest(BaseModel):
    name: str


class AppStateRequest(BaseModel):
    values: dict[str, str]


class IndexImportDeleteRequest(BaseModel):
    path: str
    collection_id: str | None = None


class DocumentExtractResponse(BaseModel):
    ok: bool
    name: str
    text: str
    chars: int
    truncated: bool


class ResearchRequest(BaseModel):
    query: str
    collections: list[str] | None = None
    depth: int = 2
    model: str | None = None
    keep_alive: str | int | None = None
    aggressive_quant: bool | None = None


class WatchStartRequest(BaseModel):
    paths: list[str] | None = None
    collection: str | None = None


class MemoryCreateRequest(BaseModel):
    text: str
    tags: list[str] | None = None


class MemoryRefreshRequest(BaseModel):
    scope: str | None = None


class UsageRecordRequest(BaseModel):
    engine: str = "ollama"
    model: str = "unknown"
    project: str | None = None
    collections: list[str] | None = None
    est_tokens: int = 0
