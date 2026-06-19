"""Pydantic models for OpenAI-compatible request/response shapes."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class Message(BaseModel):
    """A single message in a chat conversation."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible /chat/completions request body (subset)."""

    messages: list[Message]
    model: str = Field(default="antigravity", description="Model identifier (ignored; proxied to CLI)")
    max_tokens: int | None = Field(default=None, description="Not enforced — CLI controls output length")
    temperature: float | None = Field(default=None)
    stream: bool = Field(default=False, description="Streaming is not supported")
    tools: list[Any] | None = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ChatCompletionMessage(BaseModel):
    """Message returned inside a choice."""

    role: Literal["assistant"] = "assistant"
    content: str


class Choice(BaseModel):
    """A single completion choice."""

    index: int = 0
    message: ChatCompletionMessage
    finish_reason: str = "stop"


class Usage(BaseModel):
    """Token-usage estimate (CLI does not report tokens — defaults to 0)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible /chat/completions response."""

    id: str = Field(default_factory=lambda: f"cliff-{uuid.uuid4().hex[:12]}")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "antigravity"
    choices: list[Choice]
    usage: Usage = Field(default_factory=Usage)


# ---------------------------------------------------------------------------
# Health endpoint model
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Response schema for GET /healthz."""

    status: str = "ok"
    version: str = "0.1.0"


# ---------------------------------------------------------------------------
# Embeddings models
# ---------------------------------------------------------------------------

class EmbeddingRequest(BaseModel):
    """OpenAI-compatible /embeddings request body."""

    input: str | list[str]
    model: str = Field(default="text-embedding-004", description="Embedding model identifier")
    encoding_format: str = Field(default="float", description="float or base64")
    dimensions: int | None = None


class EmbeddingObject(BaseModel):
    """A single embedding in the response."""

    object: Literal["embedding"] = "embedding"
    index: int = 0
    embedding: list[float]


class EmbeddingUsage(BaseModel):
    """Token usage for embeddings (CLI does not report tokens)."""

    prompt_tokens: int = 0
    total_tokens: int = 0


class EmbeddingResponse(BaseModel):
    """OpenAI-compatible /embeddings response."""

    object: Literal["list"] = "list"
    data: list[EmbeddingObject]
    model: str
    usage: EmbeddingUsage = Field(default_factory=EmbeddingUsage)


# ---------------------------------------------------------------------------
# Models list endpoint models
# ---------------------------------------------------------------------------

class ModelObject(BaseModel):
    """A single model entry in the /v1/models list."""

    id: str
    object: Literal["model"] = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "antigravity"


class ModelsListResponse(BaseModel):
    """OpenAI-compatible /v1/models response."""

    object: Literal["list"] = "list"
    data: list[ModelObject]
