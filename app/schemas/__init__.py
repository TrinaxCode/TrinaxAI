"""Pydantic models for TrinaxAI API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[dict]
    stream: bool = False
    collections: list[str] | None = None


class CollectionCreateRequest(BaseModel):
    name: str


class CollectionUpdateRequest(BaseModel):
    name: str


class AppStateRequest(BaseModel):
    values: dict[str, str]


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
