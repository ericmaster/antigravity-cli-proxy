r"""Invokes the Antigravity CLI (agy) as an async subprocess.

For prompts larger than 8 KB the text is piped via stdin to avoid
shell argument-length limits; smaller prompts use the ``--print`` flag
directly.

Environment variables (all optional):
    ANTIGRAVITY_COMMAND  — CLI executable name (default: ``\"agy\"``)
    ANTIGRAVITY_TIMEOUT  — Per-call timeout in seconds (default: ``120``)
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

# Threshold above which we pipe the prompt via stdin instead of --print
_STDIN_THRESHOLD = 8 * 1024  # 8 KB

logger = logging.getLogger("antigravity-cli-proxy.cli_invoker")


@dataclass
class CliResult:
    """Outcome of a single CLI invocation."""

    output: str
    exit_code: int
    stderr: str
    timed_out: bool = False


class CliInvoker:
    """Async wrapper around the Antigravity CLI (agy).

    Parameters
    ----------
    command :
        CLI executable name or full path (default read from env or ``\"agy\"``).
    timeout :
        Maximum seconds to wait for a single invocation (default from env or 120).
    model :
        Optional model override passed via ``--model``.
    """

    def __init__(
        self,
        command: str | None = None,
        timeout: float | None = None,
        model: str | None = None,
    ) -> None:
        self.command = command or os.getenv("ANTIGRAVITY_COMMAND", "agy")
        self.timeout = float(timeout if timeout is not None else os.getenv("ANTIGRAVITY_TIMEOUT", "120"))
        self.model = model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def invoke(self, prompt: str) -> CliResult:
        """Run *prompt* through the CLI and return the result."""
        use_stdin = len(prompt) > _STDIN_THRESHOLD
        return await self._run(prompt, use_stdin=use_stdin)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_args(self, use_stdin: bool) -> list[str]:
        """Build the CLI argument list.

        When *use_stdin* is True we omit the ``-p`` prompt text so that
        agy reads from stdin instead.
        """
        args = [self.command, "--print"]
        if not use_stdin:
            # placeholder removed — prompt will be appended
            pass
        args.append("--dangerously-skip-permissions")
        args.append(f"--print-timeout={int(self.timeout)}s")
        if self.model:
            args.extend(["--model", self.model])
        return args

    async def _run(self, prompt: str, use_stdin: bool) -> CliResult:
        """Execute the subprocess and collect output."""
        args = self._build_args(use_stdin)

        # Insert prompt as argv for the flag path
        if not use_stdin:
            # args: [cmd, --print, --dangerously-skip-permissions, ...]
            # Insert prompt after --print
            args.insert(2, prompt)

        stdin_data = prompt.encode() if use_stdin else None
        stdin_pipe = asyncio.subprocess.PIPE if use_stdin else asyncio.subprocess.DEVNULL

        logger.debug(
            "CLI invoke: command=%s mode=%s prompt_len=%d",
            self.command,
            "stdin" if use_stdin else "flag",
            len(prompt),
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                args[0],
                *args[1:],
                stdin=stdin_pipe,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, OSError) as exc:
            msg = str(exc)
            logger.error("CLI executable not found or failed to spawn: %s", msg)
            return CliResult(
                output="",
                exit_code=127 if isinstance(exc, FileNotFoundError) else 1,
                stderr=msg,
                timed_out=False,
            )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=stdin_data),
                timeout=self.timeout,
            )
            output = stdout_bytes.decode(errors="replace").strip()
            stderr = stderr_bytes.decode(errors="replace").strip()

            logger.info(
                "CLI call completed: exit=%d, output_len=%d, stderr_len=%d",
                proc.returncode or 0,
                len(output),
                len(stderr),
            )

            return CliResult(
                output=output,
                exit_code=proc.returncode or 0,
                stderr=stderr,
                timed_out=False,
            )

        except asyncio.TimeoutError:
            logger.warning("CLI invocation timed out after %.1f s", self.timeout)
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            return CliResult(
                output="",
                exit_code=-1,
                stderr=f"Timeout after {self.timeout} seconds",
                timed_out=True,
            )
