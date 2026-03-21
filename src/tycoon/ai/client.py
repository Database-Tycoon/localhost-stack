"""LM Studio client wrapper for tycoon ai commands.

Uses the OpenAI-compatible API that LM Studio exposes at localhost:1234.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx

LMSTUDIO_BASE_URL = "http://localhost:1234/v1"


@dataclass
class ModelInfo:
    """Metadata for a model available in LM Studio."""

    id: str
    state: str = "unknown"
    arch: str = ""
    quantization: str = ""
    max_context_length: int = 0

    @property
    def loaded(self) -> bool:
        return self.state == "loaded"


@dataclass
class LMStudioStatus:
    """Snapshot of the local LM Studio environment."""

    running: bool
    models: list[ModelInfo] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.running and any(m.loaded for m in self.models)

    @property
    def loaded_models(self) -> list[ModelInfo]:
        return [m for m in self.models if m.loaded]


def is_server_running() -> bool:
    """Check if LM Studio's local server is responding."""
    try:
        resp = httpx.get(f"{LMSTUDIO_BASE_URL}/models", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def list_models() -> list[ModelInfo]:
    """Return models available in LM Studio with metadata."""
    try:
        resp = httpx.get(f"{LMSTUDIO_BASE_URL}/models", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = []
            for m in data.get("data", []):
                models.append(
                    ModelInfo(
                        id=m.get("id", "unknown"),
                        state=m.get("state", "unknown"),
                        arch=m.get("arch", ""),
                        quantization=m.get("quantization", ""),
                        max_context_length=m.get("max_context_length", 0),
                    )
                )
            return models
    except Exception:
        pass
    return []


def get_status() -> LMStudioStatus:
    """Gather a full status snapshot."""
    running = is_server_running()
    models = list_models() if running else []
    return LMStudioStatus(running=running, models=models)


def chat(messages: list[dict[str, str]], model: str | None = None, stream: bool = False) -> str:
    """Send a chat completion request to LM Studio. Returns the assistant message content.

    If no model is specified, LM Studio uses whatever model is currently loaded.
    """
    payload: dict = {"messages": messages, "stream": stream}
    if model:
        payload["model"] = model

    resp = httpx.post(
        f"{LMSTUDIO_BASE_URL}/chat/completions",
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def chat_stream(
    messages: list[dict[str, str]],
    model: str | None = None,
) -> Iterator[str]:
    """Stream a chat completion from LM Studio, yielding content chunks.

    Uses the same ``/v1/chat/completions`` endpoint with ``stream=True``
    and parses the SSE (server-sent events) response. Each yielded value
    is a non-empty content string from a single delta.
    """
    payload: dict = {"messages": messages, "stream": True}
    if model:
        payload["model"] = model

    with httpx.stream(
        "POST",
        f"{LMSTUDIO_BASE_URL}/chat/completions",
        json=payload,
        timeout=120,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            # SSE lines look like "data: {...}" or "data: [DONE]"
            if not line.startswith("data: "):
                continue
            data_str = line[len("data: "):]
            if data_str.strip() == "[DONE]":
                return
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            content = (
                data.get("choices", [{}])[0]
                .get("delta", {})
                .get("content", "")
            )
            if content:
                yield content
