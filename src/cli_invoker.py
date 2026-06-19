"""cli_invoker — DEPRECATED.

The agy CLI backend has been replaced by direct OpenRouter API calls in
main.py. This module is retained as a stub to avoid breaking any external
imports that reference CliInvoker or CliResult; it is not used at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CliResult:
    """Stub: unused since Phase 3 (OpenRouter backend)."""

    output: str = ""
    exit_code: int = 0
    stderr: str = ""
    timed_out: bool = False


class CliInvoker:
    """Stub: unused since Phase 3 (OpenRouter backend)."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        pass

    async def invoke(self, prompt: str) -> CliResult:  # noqa: ARG002
        raise NotImplementedError(
            "CliInvoker is no longer active. The proxy now calls OpenRouter directly."
        )
