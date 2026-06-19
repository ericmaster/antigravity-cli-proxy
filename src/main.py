"""FastAPI application entrypoint for antigravity-cli-proxy proxy.

Phase 3: OpenRouter backend — replaces agy CLI shelling with direct
httpx calls to https://openrouter.ai/api/v1.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionMessage,
    Choice,
    Usage,
    HealthResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingObject,
    EmbeddingUsage,
    ModelObject,
    ModelsListResponse,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PORT = int(os.getenv("PORT", "3120"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
PROXY_TIMEOUT = float(os.getenv("PROXY_TIMEOUT", "30"))
VERSION = "0.4.0"

_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
_OPENROUTER_REFERER = "https://nimblersoft.com"
_OPENROUTER_TITLE = "Nimblersoft agentmemory"

# Embedding stub dimensions (BM25 fallback)
_EMBEDDING_DIMS = 768

# Models cache: (timestamp, list[dict])
_models_cache: tuple[float, list[dict]] | None = None
_MODELS_CACHE_TTL = 600  # 10 minutes

# Static fallback model list (used when OpenRouter /v1/models is unreachable)
_FALLBACK_MODELS: list[dict] = [
    {"id": "openai/gpt-4o"},
    {"id": "anthropic/claude-3.5-sonnet"},
    {"id": "google/gemini-2.0-flash"},
]

# Logging setup
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("antigravity-cli-proxy")

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="antigravity-cli-proxy",
    description="OpenAI-compatible proxy for OpenRouter",
    version=VERSION,
)


# ---------------------------------------------------------------------------
# Token helper
# ---------------------------------------------------------------------------

def _get_token() -> str | None:
    """Read the OpenRouter token from the environment (injected by infisical run)."""
    return os.getenv("AGENTMEMORY_OPENROUTER_TOKEN") or None


def _openrouter_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "HTTP-Referer": _OPENROUTER_REFERER,
        "X-Title": _OPENROUTER_TITLE,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Models cache helpers
# ---------------------------------------------------------------------------

async def _fetch_openrouter_models() -> list[dict]:
    """Fetch model list from OpenRouter; return fallback list on failure."""
    global _models_cache

    now = time.monotonic()
    if _models_cache is not None:
        ts, cached = _models_cache
        if now - ts < _MODELS_CACHE_TTL:
            return cached

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{_OPENROUTER_BASE}/models")
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            _models_cache = (now, data)
            logger.info("Fetched %d models from OpenRouter (cached for %ds)", len(data), _MODELS_CACHE_TTL)
            return data
        else:
            logger.warning("OpenRouter /v1/models returned %d — using fallback list", resp.status_code)
    except Exception as exc:
        logger.warning("Failed to fetch OpenRouter models (%s) — using fallback list", exc)

    _models_cache = (now, _FALLBACK_MODELS)
    return _FALLBACK_MODELS


# ---------------------------------------------------------------------------
# Embedding stub
# ---------------------------------------------------------------------------

def _stub_embeddings(texts: list[str], dims: int = _EMBEDDING_DIMS) -> list[list[float]]:
    """Return zero-vector stub embeddings (BM25-only fallback)."""
    logger.warning(
        "Returning zero-vector stub embeddings for %d text(s) (dims=%d). "
        "BM25-only mode — semantic search disabled.",
        len(texts),
        dims,
    )
    return [[0.0] * dims for _ in texts]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check — reports token presence without revealing it."""
    token = _get_token()
    if token:
        status = "ok"
    else:
        status = "degraded"
        logger.warning(
            "AGENTMEMORY_OPENROUTER_TOKEN is not set — completions will return 503"
        )
    return HealthResponse(status=status, version=VERSION)


@app.get("/v1/models", response_model=ModelsListResponse)
async def list_models() -> ModelsListResponse:
    """OpenAI-compatible model listing — proxied from OpenRouter (10-min cache)."""
    models = await _fetch_openrouter_models()
    now = int(time.time())
    data = [
        ModelObject(id=m["id"], created=now, owned_by="openrouter")
        for m in models
    ]
    return ModelsListResponse(data=data)


@app.post("/v1/chat/completions")
async def chat_completions_v1(request: ChatCompletionRequest) -> JSONResponse:
    """OpenAI-compatible chat completions — forwarded to OpenRouter."""
    return await _handle_chat_completions(request)


@app.post("/chat/completions")
async def chat_completions_legacy(request: ChatCompletionRequest) -> JSONResponse:
    """Alias for /v1/chat/completions — kept for backward compatibility."""
    return await _handle_chat_completions(request)


async def _handle_chat_completions(request: ChatCompletionRequest) -> JSONResponse:
    """Forward the request body to OpenRouter and pass the response through."""
    token = _get_token()
    if not token:
        logger.error(
            "AGENTMEMORY_OPENROUTER_TOKEN is not set — returning 503. "
            "Ensure the service is started via start.sh with infisical run."
        )
        raise HTTPException(
            status_code=503,
            detail="OpenRouter token not configured. Service is starting in degraded mode.",
        )

    t0 = time.monotonic()
    logger.info(
        "Received /v1/chat/completions: model=%s messages=%d",
        request.model,
        len(request.messages),
    )

    # Build the payload — pass through as-is so clients can send any model
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": [m.model_dump() for m in request.messages],
    }
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.stream:
        # Streaming not yet supported — downgrade silently
        logger.warning("stream=true requested but not supported; returning non-streaming response")
    if request.tools:
        payload["tools"] = request.tools

    try:
        async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
            resp = await client.post(
                f"{_OPENROUTER_BASE}/chat/completions",
                headers=_openrouter_headers(token),
                json=payload,
            )
    except httpx.TimeoutException:
        logger.error("OpenRouter request timed out after %.1fs", PROXY_TIMEOUT)
        raise HTTPException(status_code=504, detail="Upstream OpenRouter timed out")
    except httpx.RequestError as exc:
        logger.error("OpenRouter request error: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream connection error: {exc}")

    elapsed_ms = (time.monotonic() - t0) * 1000
    logger.info(
        "OpenRouter response: status=%d elapsed=%.0fms",
        resp.status_code,
        elapsed_ms,
    )

    if resp.status_code != 200:
        # Pass upstream error through as-is
        return JSONResponse(status_code=resp.status_code, content=resp.json())

    return JSONResponse(status_code=200, content=resp.json())


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def embeddings_v1(request: EmbeddingRequest) -> EmbeddingResponse:
    """OpenAI-compatible embeddings endpoint.

    Attempts to forward to OpenRouter's /v1/embeddings if the token is set.
    OpenRouter returns 401 with a missing-header error when the token is wrong;
    it returns a structured error body (not 404) indicating the endpoint exists.
    On any failure, falls back to zero-vector stubs (BM25-only mode) so
    agentmemory continues to function.
    """
    texts: list[str] = (
        [request.input] if isinstance(request.input, str) else list(request.input)
    )
    if not texts:
        raise HTTPException(status_code=422, detail="input must be a non-empty string or list")

    model = request.model or "text-embedding-3-small"
    total_chars = sum(len(t) for t in texts)

    logger.info(
        "Received /v1/embeddings: model=%s texts=%d total_chars=%d",
        model,
        len(texts),
        total_chars,
    )

    token = _get_token()
    vectors: list[list[float]] | None = None
    dims = _EMBEDDING_DIMS

    if token:
        try:
            async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
                resp = await client.post(
                    f"{_OPENROUTER_BASE}/embeddings",
                    headers=_openrouter_headers(token),
                    json={"model": model, "input": texts},
                )
            if resp.status_code == 200:
                body = resp.json()
                embed_data = body.get("data", [])
                vectors = [item["embedding"] for item in embed_data]
                dims = len(vectors[0]) if vectors else _EMBEDDING_DIMS
                logger.info(
                    "OpenRouter embeddings OK: count=%d dims=%d",
                    len(vectors),
                    dims,
                )
            else:
                body = resp.json() if resp.content else {}
                err_msg = body.get("error", {}).get("message", resp.text[:200])
                logger.warning(
                    "OpenRouter /v1/embeddings returned %d (%s) — falling back to zero-vector stubs",
                    resp.status_code,
                    err_msg,
                )
        except Exception as exc:
            logger.warning(
                "OpenRouter embeddings request failed (%s) — falling back to zero-vector stubs",
                exc,
            )
    else:
        logger.warning(
            "AGENTMEMORY_OPENROUTER_TOKEN not set — returning zero-vector stubs (BM25-only mode)"
        )

    if vectors is None:
        vectors = _stub_embeddings(texts)
        dims = _EMBEDDING_DIMS

    data = [EmbeddingObject(index=i, embedding=vec) for i, vec in enumerate(vectors)]

    return EmbeddingResponse(
        data=data,
        model=model,
        usage=EmbeddingUsage(
            prompt_tokens=total_chars // 4,
            total_tokens=total_chars // 4,
        ),
    )


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the proxy server via ``python -m src`` or ``cliff``."""
    import uvicorn

    token = _get_token()
    if not token:
        logger.warning(
            "AGENTMEMORY_OPENROUTER_TOKEN is not set at startup. "
            "Completions will return 503 until the token is injected. "
            "Use start.sh (which wraps infisical run) to launch this service."
        )
    else:
        logger.info("AGENTMEMORY_OPENROUTER_TOKEN is set — OpenRouter backend ready.")

    logger.info(
        "Starting antigravity-cli-proxy (OpenRouter backend) on port %s (log level: %s, timeout: %ss)",
        PORT,
        LOG_LEVEL,
        PROXY_TIMEOUT,
    )
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=PORT,
        log_level=LOG_LEVEL.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
