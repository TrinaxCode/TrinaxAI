"""Pydantic contracts for the public HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

import config


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[dict] = Field(min_length=1, max_length=100)
    stream: bool = False
    collections: list[str] | None = Field(default=None, max_length=50)
    keep_alive: str | int | None = None
    aggressive_quant: bool | None = None
    mode: Literal["auto", "knowledge", "model"] = "auto"

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
            has_user = has_user or role == "user"
            if len(content) > 100_000:
                raise ValueError("A single message is too large (maximum 100,000 characters).")
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


class AppStateOperation(BaseModel):
    """One atomic shared-state mutation.

    Deletes are represented explicitly so a removed setting cannot be
    resurrected by a stale full-state snapshot from another device.
    """

    op: Literal["set", "delete"]
    key: str = Field(min_length=3, max_length=200, pattern=r"^tc-")
    value: str | None = None

    @model_validator(mode="after")
    def validate_value(self) -> "AppStateOperation":
        if self.op == "set" and not isinstance(self.value, str):
            raise ValueError("A set operation requires a string value.")
        if self.op == "delete" and self.value is not None:
            raise ValueError("A delete operation cannot include a value.")
        return self


class AppStateRequest(BaseModel):
    """Versioned app-state update, with a constrained legacy migration path."""

    schema_version: Literal[2] | None = None
    device_id: str | None = Field(default=None, min_length=8, max_length=128)
    base_revision: int | None = Field(default=None, ge=0)
    operations: list[AppStateOperation] | None = Field(default=None, max_length=2000)
    # Legacy clients used ``{"values": {...}}``.  The service accepts it only
    # with optimistic concurrency (or against a pristine revision-zero store).
    values: dict[str, str] | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "AppStateRequest":
        has_operations = self.operations is not None
        has_values = self.values is not None
        if has_operations == has_values:
            raise ValueError("Provide exactly one of operations or values.")
        if has_operations and self.base_revision is None:
            raise ValueError("base_revision is required for incremental updates.")
        return self


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
    query: str = Field(min_length=1, max_length=10_000)
    search_query: str | None = Field(default=None, max_length=2_000)
    context: str | None = Field(default=None, max_length=12_000)
    collections: list[str] | None = None
    depth: int = 2
    web_search: bool | None = None
    include_local: bool = False
    model: str | None = None
    keep_alive: str | int | None = None
    aggressive_quant: bool | None = None


class WatchStartRequest(BaseModel):
    paths: list[str] | None = None
    collection: str | None = None


class AgentRequest(BaseModel):
    """A turn for the agentic assistant (file/shell tool-use over a workspace)."""

    messages: list[dict] = Field(min_length=1, max_length=100)
    workspace: str | None = None
    model: str | None = None
    max_steps: int = Field(default=25, ge=1, le=100)
    yolo: bool = False
    web_search: bool = False
    knowledge_search: bool = True
    deep_research: bool = False

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages: list[dict]) -> list[dict]:
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
            has_user = has_user or role == "user"
        if not has_user:
            raise ValueError("At least one user message is required.")
        return messages


class AgentApprovalRequest(BaseModel):
    """Approve or reject a pending dangerous agent action."""

    session_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    approval_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    approved: bool


class MemoryCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=config.MEMORY_TEXT_MAX_CHARS)
    tags: list[str] | None = Field(default=None, max_length=config.MEMORY_MAX_TAGS)
    kind: Literal["fact", "preference", "decision", "note"] = "note"
    provenance: Literal["manual", "inferred"] = "manual"
    expires_at: float | None = Field(default=None, gt=0)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str] | None) -> list[str] | None:
        if tags is None:
            return None
        cleaned: list[str] = []
        for tag in tags:
            value = str(tag).strip()
            if len(value) > config.MEMORY_TAG_MAX_CHARS:
                raise ValueError(f"Memory tags cannot exceed {config.MEMORY_TAG_MAX_CHARS} characters.")
            if value:
                cleaned.append(value)
        return cleaned


class MemoryUpdateRequest(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=config.MEMORY_TEXT_MAX_CHARS)
    tags: list[str] | None = Field(default=None, max_length=config.MEMORY_MAX_TAGS)
    kind: Literal["fact", "preference", "decision", "note"] | None = None
    expires_at: float | None = Field(default=None, gt=0)
    clear_expiration: bool = False

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str] | None) -> list[str] | None:
        return MemoryCreateRequest.validate_tags(tags)

    @model_validator(mode="after")
    def validate_change(self):
        if not any(
            value is not None
            for value in (self.text, self.tags, self.kind, self.expires_at)
        ) and not self.clear_expiration:
            raise ValueError("At least one memory field must change.")
        return self


class MemoryContextRequest(BaseModel):
    query: str = Field(min_length=1, max_length=32_000)
    max_entries: int = Field(default=8, ge=1, le=20)


class MemoryRefreshRequest(BaseModel):
    scope: str | None = None


class UsageRecordRequest(BaseModel):
    engine: str = "ollama"
    model: str = "unknown"
    project: str | None = None
    collections: list[str] | None = None
    est_tokens: int = 0
