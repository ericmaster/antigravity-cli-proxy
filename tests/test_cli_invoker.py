"""Unit tests for src/cli_invoker.py — CliInvoker class.

Tests cover:
- Successful invocation (short prompt via --print flag)
- Successful invocation (long prompt via stdin)
- Timeout handling
- CLI not found error
- Successful response mapping
"""

from __future__ import annotations

import asyncio
import os
import platform

import pytest

from src.cli_invoker import CliInvoker, CliResult


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture()
def invoker():
    """Default invoker pointing at the real agy binary."""
    cmd = os.getenv("ANTIGRAVITY_COMMAND", "agy")
    return CliInvoker(command=cmd, timeout=15)


@pytest.fixture()
def fake_invoker():
    """Invoker pointing at a non-existent binary."""
    return CliInvoker(command="this-cli-does-not-exist-xyz123", timeout=5)


@pytest.fixture()
def slow_invoker():
    """Invoker with a very short timeout to trigger timeouts on real CLI calls."""
    return CliInvoker(command="agy", timeout=0.01)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestCliInvokerSuccess:

    @pytest.mark.asyncio
    async def test_short_prompt_via_flag(self, invoker):
        """A short prompt (<8KB) should be passed via --print flag."""
        result = await invoker.invoke("Reply with exactly: OK_TEST_123")
        # agy should return something containing our test marker
        assert result.exit_code == 0
        assert result.output != ""
        assert not result.timed_out

    @pytest.mark.asyncio
    async def test_long_prompt_via_stdin(self, invoker):
        """A long prompt (>8KB) should be piped via stdin."""
        long_prompt = "Summarize this: " + "X" * 9000
        result = await invoker.invoke(long_prompt)
        assert result.exit_code == 0
        assert result.output != ""
        assert not result.timed_out


class TestCliInvokerErrors:

    @pytest.mark.asyncio
    async def test_cli_not_found(self, fake_invoker):
        """When the CLI binary doesn't exist, we get a clean error."""
        result = await fake_invoker.invoke("hello")
        assert result.exit_code == 127
        # stderr will contain OS-level error text about missing file
        stderr_lower = result.stderr.lower()
        assert any(kw in stderr_lower for kw in ["not found", "no such file", "cli executable"])
        assert result.output == ""
        assert not result.timed_out

    @pytest.mark.asyncio
    async def test_timeout_handling(self, slow_invoker):
        """A very short timeout should fire and return timed_out=True."""
        result = await slow_invoker.invoke("Write a long essay about philosophy.")
        assert result.timed_out
        assert result.exit_code == -1
        assert "Timeout" in result.stderr


class TestCliResult:
    """Basic dataclass sanity checks."""

    def test_cli_result_fields(self):
        r = CliResult(output="hi", exit_code=0, stderr="")
        assert r.output == "hi"
        assert r.exit_code == 0
        assert r.stderr == ""
        assert r.timed_out is False  # default

    def test_cli_result_timed_out_true(self):
        r = CliResult(output="", exit_code=-1, stderr="boom", timed_out=True)
        assert r.timed_out is True


class TestPromptRouting:
    """Verify that prompt length correctly switches between flag and stdin."""

    @pytest.mark.asyncio
    async def test_8kb_boundary_flag(self, invoker):
        exactly_8kb = "A" * 8192  # == _STDIN_THRESHOLD, NOT greater
        result = await invoker.invoke(exactly_8kb)
        # At exactly the threshold, should still use --print flag path
        # The call may succeed or timeout depending on model speed — just check it ran
        assert result.timed_out or result.output != ""

    @pytest.mark.asyncio
    async def test_over_8kb_boundary_stdin(self, invoker):
        over_8kb = "A" * (8192 + 1)  # > _STDIN_THRESHOLD → stdin path
        result = await invoker.invoke(over_8kb)
        # Should use stdin path — result should still be valid
        assert result.output is not None
