"""Tests for tycoon ai — LM Studio client and commands."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from tycoon.ai.client import (
    LMSTUDIO_BASE_URL,
    LMStudioStatus,
    ModelInfo,
    get_status,
    is_server_running,
    list_models,
    chat,
)
from tycoon.cli import app


# ---------------------------------------------------------------------------
# ModelInfo
# ---------------------------------------------------------------------------

class TestModelInfo:
    def test_loaded_when_state_loaded(self):
        m = ModelInfo(id="qwen2.5-coder", state="loaded")
        assert m.loaded is True

    def test_not_loaded_when_state_not_loaded(self):
        m = ModelInfo(id="qwen2.5-coder", state="not-loaded")
        assert m.loaded is False

    def test_not_loaded_when_state_unknown(self):
        m = ModelInfo(id="qwen2.5-coder")
        assert m.loaded is False


# ---------------------------------------------------------------------------
# LMStudioStatus
# ---------------------------------------------------------------------------

class TestLMStudioStatus:
    def test_ready_when_running_and_model_loaded(self):
        st = LMStudioStatus(
            running=True,
            models=[ModelInfo(id="test", state="loaded")],
        )
        assert st.ready is True

    def test_not_ready_when_not_running(self):
        st = LMStudioStatus(running=False)
        assert st.ready is False

    def test_not_ready_when_no_loaded_models(self):
        st = LMStudioStatus(
            running=True,
            models=[ModelInfo(id="test", state="not-loaded")],
        )
        assert st.ready is False

    def test_loaded_models_filters_correctly(self):
        st = LMStudioStatus(
            running=True,
            models=[
                ModelInfo(id="a", state="loaded"),
                ModelInfo(id="b", state="not-loaded"),
                ModelInfo(id="c", state="loaded"),
            ],
        )
        assert [m.id for m in st.loaded_models] == ["a", "c"]

    def test_loaded_models_empty_when_none_loaded(self):
        st = LMStudioStatus(running=True, models=[])
        assert st.loaded_models == []


# ---------------------------------------------------------------------------
# is_server_running
# ---------------------------------------------------------------------------

class TestIsServerRunning:
    def test_returns_true_when_server_responds(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("tycoon.ai.client.httpx.get", return_value=mock_resp):
            assert is_server_running() is True

    def test_returns_false_when_server_down(self):
        with patch("tycoon.ai.client.httpx.get", side_effect=Exception("refused")):
            assert is_server_running() is False

    def test_returns_false_on_non_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("tycoon.ai.client.httpx.get", return_value=mock_resp):
            assert is_server_running() is False


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------

class TestListModels:
    def test_parses_model_list(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "id": "qwen2.5-coder-7b",
                    "state": "loaded",
                    "arch": "qwen2",
                    "quantization": "Q4_K_M",
                    "max_context_length": 32768,
                },
                {
                    "id": "llama-3.1-8b",
                    "state": "not-loaded",
                },
            ]
        }
        with patch("tycoon.ai.client.httpx.get", return_value=mock_resp):
            models = list_models()
            assert len(models) == 2
            assert models[0].id == "qwen2.5-coder-7b"
            assert models[0].state == "loaded"
            assert models[0].quantization == "Q4_K_M"
            assert models[0].max_context_length == 32768
            assert models[1].id == "llama-3.1-8b"
            assert models[1].loaded is False

    def test_returns_empty_on_error(self):
        with patch("tycoon.ai.client.httpx.get", side_effect=Exception("timeout")):
            assert list_models() == []

    def test_returns_empty_on_non_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("tycoon.ai.client.httpx.get", return_value=mock_resp):
            assert list_models() == []


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_status_when_server_running_with_models(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"id": "test-model", "state": "loaded"}]
        }
        with patch("tycoon.ai.client.httpx.get", return_value=mock_resp):
            st = get_status()
            assert st.running is True
            assert len(st.models) == 1
            assert st.ready is True

    def test_status_when_server_down(self):
        with patch("tycoon.ai.client.httpx.get", side_effect=Exception("refused")):
            st = get_status()
            assert st.running is False
            assert st.models == []
            assert st.ready is False


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------

class TestChat:
    def test_sends_request_and_returns_content(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}]
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("tycoon.ai.client.httpx.post", return_value=mock_resp) as mock_post:
            result = chat([{"role": "user", "content": "Hi"}])
            assert result == "Hello!"
            call_args = mock_post.call_args
            assert call_args[0][0] == f"{LMSTUDIO_BASE_URL}/chat/completions"
            payload = call_args[1]["json"]
            assert "model" not in payload
            assert payload["stream"] is False

    def test_passes_model_when_specified(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_resp.raise_for_status = MagicMock()
        with patch("tycoon.ai.client.httpx.post", return_value=mock_resp) as mock_post:
            chat([{"role": "user", "content": "Hi"}], model="my-model")
            payload = mock_post.call_args[1]["json"]
            assert payload["model"] == "my-model"


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

class TestAIStatusCommand:
    def test_status_when_server_running(self, cli_runner):
        mock_status = LMStudioStatus(
            running=True,
            models=[ModelInfo(id="test-model", state="loaded", quantization="Q4_K_M", max_context_length=32768)],
        )
        with patch("tycoon.commands.ai.get_status", return_value=mock_status):
            result = cli_runner.invoke(app, ["ai", "status"])
            assert result.exit_code == 0
            assert "test-model" in result.stdout

    def test_status_when_server_down(self, cli_runner):
        mock_status = LMStudioStatus(running=False)
        with patch("tycoon.commands.ai.get_status", return_value=mock_status):
            result = cli_runner.invoke(app, ["ai", "status"])
            assert result.exit_code == 0
            assert "not running" in result.stdout or "FAIL" in result.stdout

    def test_status_no_loaded_models(self, cli_runner):
        mock_status = LMStudioStatus(
            running=True,
            models=[ModelInfo(id="test", state="not-loaded")],
        )
        with patch("tycoon.commands.ai.get_status", return_value=mock_status):
            result = cli_runner.invoke(app, ["ai", "status"])
            assert result.exit_code == 0
            assert "no model loaded" in result.stdout or "WARN" in result.stdout


class TestAISetupCommand:
    def test_setup_succeeds_when_ready(self, cli_runner):
        mock_status = LMStudioStatus(
            running=True,
            models=[ModelInfo(id="test-model", state="loaded")],
        )
        with patch("tycoon.commands.ai.get_status", return_value=mock_status):
            result = cli_runner.invoke(app, ["ai", "setup"])
            assert result.exit_code == 0
            assert "ready" in result.stdout.lower()

    def test_setup_fails_when_server_down(self, cli_runner):
        mock_status = LMStudioStatus(running=False)
        with patch("tycoon.commands.ai.get_status", return_value=mock_status):
            result = cli_runner.invoke(app, ["ai", "setup"])
            assert result.exit_code == 1

    def test_setup_fails_when_no_model_loaded(self, cli_runner):
        mock_status = LMStudioStatus(
            running=True,
            models=[ModelInfo(id="test", state="not-loaded")],
        )
        with patch("tycoon.commands.ai.get_status", return_value=mock_status):
            result = cli_runner.invoke(app, ["ai", "setup"])
            assert result.exit_code == 1
