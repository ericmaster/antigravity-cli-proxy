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

    status: Literal["ok"] = "ok"
    version: str = "0.1.0"
