"""FastAPI application entrypoint for antigravity-cli-proxy proxy.

Phase 2: Full implementation of the OpenAI -> antigravity CLI pipe.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
import uuid

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionMessage,
    Choice,
    Usage,
    HealthResponse,
)
from .cli_invoker import CliInvoker, CliResult

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PORT = int(os.getenv("PORT", "3120"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
ANTIGRAVITY_COMMAND = os.getenv("ANTIGRAVITY_COMMAND", "agy")
ANTIGRAVITY_TIMEOUT = float(os.getenv("ANTIGRAVITY_TIMEOUT", "120"))
VERSION = "0.2.0"

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
    description="OpenAI-compatible proxy for antigravity CLI",
    version=VERSION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def messages_to_prompt(messages: list[dict]) -> str:
    """Concatenate a list of OpenAI messages into a single prompt string.

    Each message is prefixed with its role so the model understands the
    conversation context.  Example::

        system: You are a helpful assistant.
        user: Hello!
        assistant: Hi there!
        user: What is 2+2?
    """
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content:
            parts.append(f"{role}: {content}")
    return "\n\n".join(parts)


def cli_result_to_response(
    result: CliResult,
    model_name: str = "antigravity",
) -> ChatCompletionResponse:
    """Convert a CliResult into an OpenAI-compatible ChatCompletionResponse.

    On success, the CLI output becomes the assistant message content.
    On failure (non-zero exit, timeout, empty output), an error message
    is returned instead.
    """
    if result.exit_code == 0 and result.output:
        content = result.output
    elif result.timed_out:
        content = f"[Error] CLI timed out after {ANTIGRAVITY_TIMEOUT} seconds."
    elif result.stderr:
        content = f"[Error] CLI failed (exit code {result.exit_code}): {result.stderr}"
    else:
        content = "[Error] CLI returned empty output with no error details."

    return ChatCompletionResponse(
        id=f"cliff-{uuid.uuid4().hex[:12]}",
        model=model_name,
        choices=[
            Choice(
                message=ChatCompletionMessage(content=content),
                finish_reason="stop",
            )
        ],
        usage=Usage(
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        ),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check — verifies antigravity CLI availability."""
    cli_available = shutil.which(ANTIGRAVITY_COMMAND) is not None
    status = "ok" if cli_available else "degraded"
    detail = ""
    if not cli_available:
        detail = f"antigravity CLI not found: {ANTIGRAVITY_COMMAND}"
    return HealthResponse(status=status, version=VERSION)


@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """OpenAI-compatible chat completions endpoint.

    Translates the incoming OpenAI request into an antigravity CLI call
    and returns the response in OpenAI format.
    """
    t0 = time.monotonic()
    prompt = messages_to_prompt([m.model_dump() for m in request.messages])

    logger.info(
        "Received /chat/completions: model=%s messages=%d prompt_len=%d",
        request.model,
        len(request.messages),
        len(prompt),
    )

    invoker = CliInvoker(
        command=ANTIGRAVITY_COMMAND,
        timeout=ANTIGRAVITY_TIMEOUT,
        model=request.model if request.model != "antigravity" else None,
    )

    result = await invoker.invoke(prompt)

    elapsed_ms = (time.monotonic() - t0) * 1000
    logger.info(
        "Response sent: exit=%d output_len=%d elapsed=%.0fms",
        result.exit_code,
        len(result.output),
        elapsed_ms,
    )

    return cli_result_to_response(result, model_name=request.model or "antigravity")


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the proxy server via ``python -m src`` or ``cliff``."""
    import uvicorn

    logger.info("Starting antigravity-cli-proxy proxy on port %s (log level: %s)", PORT, LOG_LEVEL)
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=PORT,
        log_level=LOG_LEVEL.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
