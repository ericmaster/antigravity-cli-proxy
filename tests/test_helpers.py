"""Unit tests for src/main.py helper functions.

Tests:
- messages_to_prompt concatenation (system + user + assistant turns)
- cli_result_to_response mapping (success, error, timeout, empty)
"""

from __future__ import annotations

import pytest

from src.main import messages_to_prompt, cli_result_to_response
from src.cli_invoker import CliResult


# ------------------------------------------------------------------
# messages_to_prompt
# ------------------------------------------------------------------

class TestMessagesToPrompt:

    def test_single_user_message(self):
        messages = [{"role": "user", "content": "Hello!"}]
        result = messages_to_prompt(messages)
        assert result == "user: Hello!"

    def test_system_plus_user(self):
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Say hi."},
        ]
        result = messages_to_prompt(messages)
        assert "system: You are helpful." in result
        assert "user: Say hi." in result
        # Separated by double newline
        assert "\n\n" in result

    def test_full_conversation(self):
        messages = [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "A programming language."},
            {"role": "user", "content": "Who created it?"},
        ]
        result = messages_to_prompt(messages)
        assert "system: Be concise." in result
        assert "user: What is Python?" in result
        assert "assistant: A programming language." in result
        assert "user: Who created it?" in result

    def test_empty_content_skipped(self):
        messages = [
            {"role": "system", "content": ""},
            {"role": "user", "content": "Hello"},
        ]
        result = messages_to_prompt(messages)
        # Empty system message should not appear
        assert "system:" not in result
        assert "user: Hello" in result

    def test_empty_messages_list(self):
        result = messages_to_prompt([])
        assert result == ""

    def test_very_long_prompt(self):
        long_text = "A" * 100_000
        messages = [{"role": "user", "content": long_text}]
        result = messages_to_prompt(messages)
        assert "user: " in result
        assert len(result) == len(long_text) + 6  # "user: " is 6 chars


# ------------------------------------------------------------------
# cli_result_to_response
# ------------------------------------------------------------------

class TestCliResultToResponse:

    def test_successful_result(self):
        result = CliResult(output="42", exit_code=0, stderr="")
        response = cli_result_to_response(result)
        assert response.choices[0].message.content == "42"
        assert response.choices[0].message.role == "assistant"
        assert response.choices[0].finish_reason == "stop"
        assert response.usage.total_tokens == 0

    def test_timeout_result(self):
        result = CliResult(output="", exit_code=-1, stderr="Timeout after 120 seconds", timed_out=True)
        response = cli_result_to_response(result)
        assert "[Error] CLI timed out" in response.choices[0].message.content

    def test_error_result_with_stderr(self):
        result = CliResult(output="", exit_code=1, stderr="Something broke")
        response = cli_result_to_response(result)
        assert "[Error] CLI failed" in response.choices[0].message.content
        assert "Something broke" in response.choices[0].message.content

    def test_empty_output_no_error(self):
        result = CliResult(output="", exit_code=0, stderr="")
        response = cli_result_to_response(result)
        assert "[Error]" in response.choices[0].message.content

    def test_custom_model_name(self):
        result = CliResult(output="hi", exit_code=0, stderr="")
        response = cli_result_to_response(result, model_name="custom-model")
        assert response.model == "custom-model"

    def test_response_has_required_fields(self):
        result = CliResult(output="ok", exit_code=0, stderr="")
        response = cli_result_to_response(result)
        assert response.id.startswith("cliff-")
        assert response.object == "chat.completion"
        assert response.created > 0
        assert len(response.choices) == 1
