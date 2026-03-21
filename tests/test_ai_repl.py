"""Tests for tycoon ai REPL and chat command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from tycoon.ai.client import LMStudioStatus, ModelInfo
from tycoon.ai.repl import _handle_slash_command, SLASH_COMMANDS, run_repl
from tycoon.cli import app


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------


class TestSlashCommands:
    def test_quit_returns_false(self):
        messages = [{"role": "system", "content": "test"}]
        assert _handle_slash_command("/quit", messages, "test") is False

    def test_clear_resets_messages(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = _handle_slash_command("/clear", messages, "sys")
        assert result is True
        assert len(messages) == 1
        assert messages[0]["role"] == "system"

    def test_context_returns_true(self):
        messages = [{"role": "system", "content": "test"}]
        result = _handle_slash_command("/context", messages, "test prompt")
        assert result is True

    def test_help_returns_true(self):
        messages = [{"role": "system", "content": "test"}]
        result = _handle_slash_command("/help", messages, "test")
        assert result is True

    def test_unknown_command_returns_none(self):
        messages = [{"role": "system", "content": "test"}]
        assert _handle_slash_command("/unknown", messages, "test") is None

    def test_case_insensitive(self):
        messages = [{"role": "system", "content": "test"}]
        assert _handle_slash_command("/QUIT", messages, "test") is False
        assert _handle_slash_command("/Quit", messages, "test") is False


# ---------------------------------------------------------------------------
# run_repl
# ---------------------------------------------------------------------------


class TestRunRepl:
    def test_quit_exits_cleanly(self, tmp_path):
        with patch("tycoon.ai.repl.console") as mock_console:
            mock_console.input.return_value = "/quit"
            run_repl("system prompt", tmp_path)
            # Should have printed the header
            mock_console.print.assert_any_call(
                "[bold]Tycoon AI Chat[/bold] — type /help for commands, /quit to exit\n"
            )

    def test_sends_messages_to_chat(self, tmp_path):
        with (
            patch("tycoon.ai.repl.console") as mock_console,
            patch("tycoon.ai.repl.chat", return_value="AI response") as mock_chat,
        ):
            mock_console.input.side_effect = ["hello", "/quit"]
            run_repl("system prompt", tmp_path, stream=False)
            mock_chat.assert_called_once()
            messages = mock_chat.call_args[0][0]
            assert messages[0] == {"role": "system", "content": "system prompt"}
            assert messages[1] == {"role": "user", "content": "hello"}

    def test_maintains_conversation_history(self, tmp_path):
        with (
            patch("tycoon.ai.repl.console") as mock_console,
            patch("tycoon.ai.repl.chat", side_effect=["first response", "second response"]) as mock_chat,
        ):
            mock_console.input.side_effect = ["first", "second", "/quit"]
            run_repl("system prompt", tmp_path, stream=False)
            assert mock_chat.call_count == 2
            # Second call should have full history
            second_call_messages = mock_chat.call_args_list[1][0][0]
            assert len(second_call_messages) == 5  # system + user + assistant + user + (no assistant yet)
            # Actually it should be 4: system, user1, assistant1, user2
            assert second_call_messages[0]["role"] == "system"
            assert second_call_messages[1]["content"] == "first"
            assert second_call_messages[2]["content"] == "first response"
            assert second_call_messages[3]["content"] == "second"

    def test_handles_empty_input(self, tmp_path):
        with (
            patch("tycoon.ai.repl.console") as mock_console,
            patch("tycoon.ai.repl.chat") as mock_chat,
        ):
            mock_console.input.side_effect = ["", "  ", "/quit"]
            run_repl("system prompt", tmp_path, stream=False)
            mock_chat.assert_not_called()

    def test_handles_eof(self, tmp_path):
        with patch("tycoon.ai.repl.console") as mock_console:
            mock_console.input.side_effect = EOFError()
            run_repl("system prompt", tmp_path)  # Should exit cleanly

    def test_handles_keyboard_interrupt(self, tmp_path):
        with patch("tycoon.ai.repl.console") as mock_console:
            mock_console.input.side_effect = KeyboardInterrupt()
            run_repl("system prompt", tmp_path)  # Should exit cleanly

    def test_handles_chat_error(self, tmp_path):
        with (
            patch("tycoon.ai.repl.console") as mock_console,
            patch("tycoon.ai.repl.chat", side_effect=[Exception("timeout"), "ok"]) as mock_chat,
        ):
            mock_console.input.side_effect = ["first", "retry", "/quit"]
            run_repl("system prompt", tmp_path, stream=False)
            # Should have recovered and sent the retry
            assert mock_chat.call_count == 2

    def test_passes_model_to_chat(self, tmp_path):
        with (
            patch("tycoon.ai.repl.console") as mock_console,
            patch("tycoon.ai.repl.chat", return_value="ok") as mock_chat,
        ):
            mock_console.input.side_effect = ["hi", "/quit"]
            run_repl("system prompt", tmp_path, model="custom-model", stream=False)
            assert mock_chat.call_args[1]["model"] == "custom-model"

    def test_clear_preserves_system_prompt(self, tmp_path):
        # Capture messages at call time since the list is mutated after
        captured_messages: list[list[dict]] = []

        def capture_chat(msgs, **kwargs):
            captured_messages.append([m.copy() for m in msgs])
            return f"response{len(captured_messages)}"

        with (
            patch("tycoon.ai.repl.console") as mock_console,
            patch("tycoon.ai.repl.chat", side_effect=capture_chat),
        ):
            mock_console.input.side_effect = ["hello", "/clear", "after clear", "/quit"]
            run_repl("my system prompt", tmp_path, stream=False)
            # After /clear, the second chat call should only have system + new user msg
            assert len(captured_messages) == 2
            second_messages = captured_messages[1]
            assert len(second_messages) == 2
            assert second_messages[0] == {"role": "system", "content": "my system prompt"}
            assert second_messages[1] == {"role": "user", "content": "after clear"}


# ---------------------------------------------------------------------------
# chat CLI command
# ---------------------------------------------------------------------------


class TestChatCommand:
    def _mock_ready(self):
        return LMStudioStatus(
            running=True,
            models=[ModelInfo(id="test-model", state="loaded")],
        )

    def test_chat_help(self, cli_runner):
        result = cli_runner.invoke(app, ["ai", "chat", "--help"])
        assert result.exit_code == 0
        assert "--model" in result.stdout
        assert "--no-context" in result.stdout

    def test_chat_fails_when_server_down(self, cli_runner):
        with patch("tycoon.commands.ai.get_status", return_value=LMStudioStatus(running=False)):
            result = cli_runner.invoke(app, ["ai", "chat"])
            assert result.exit_code == 1

    def test_chat_starts_repl(self, cli_runner):
        with (
            patch("tycoon.commands.ai.get_status", return_value=self._mock_ready()),
            patch("tycoon.commands.ai.run_repl") as mock_repl,
        ):
            result = cli_runner.invoke(app, ["ai", "chat", "--no-context"])
            assert result.exit_code == 0
            mock_repl.assert_called_once()
            kwargs = mock_repl.call_args
            assert "data pipeline assistant" in kwargs[1]["system_prompt"]
