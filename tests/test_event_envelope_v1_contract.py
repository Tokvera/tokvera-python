from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from tokvera.track import track_anthropic, track_gemini, track_openai


@dataclass
class _OpenAIUsage:
    prompt_tokens: int = 8
    completion_tokens: int = 6
    total_tokens: int = 14


@dataclass
class _OpenAIResponse:
    model: str = "gpt-4o-mini"
    usage: _OpenAIUsage = field(default_factory=_OpenAIUsage)


class _OpenAICompletions:
    def __init__(self, response: Any) -> None:
        self._response = response

    def create(self, *args: Any, **kwargs: Any) -> Any:
        return self._response


class _OpenAIChat:
    def __init__(self, response: Any) -> None:
        self.completions = _OpenAICompletions(response)


class _OpenAIResponses:
    def __init__(self, response: Any) -> None:
        self._response = response

    def create(self, *args: Any, **kwargs: Any) -> Any:
        return self._response


class _OpenAIClient:
    def __init__(self, response: Any) -> None:
        self.chat = _OpenAIChat(response)
        self.responses = _OpenAIResponses(response)


@dataclass
class _AnthropicUsage:
    input_tokens: int = 11
    output_tokens: int = 9


@dataclass
class _AnthropicResponse:
    model: str = "claude-3-5-sonnet-latest"
    usage: _AnthropicUsage = field(default_factory=_AnthropicUsage)


class _AnthropicMessages:
    def __init__(self, response: Any) -> None:
        self._response = response

    def create(self, *args: Any, **kwargs: Any) -> Any:
        return self._response


class _AnthropicClient:
    def __init__(self, response: Any) -> None:
        self.messages = _AnthropicMessages(response)


@dataclass
class _GeminiUsage:
    prompt_token_count: int = 13
    candidates_token_count: int = 7
    total_token_count: int = 20


@dataclass
class _GeminiResponse:
    model_version: str = "gemini-2.0-flash"
    usage_metadata: _GeminiUsage = field(default_factory=_GeminiUsage)


class _GeminiModels:
    def __init__(self, response: Any) -> None:
        self._response = response

    def generate_content(self, *args: Any, **kwargs: Any) -> Any:
        return self._response


class _GeminiClient:
    def __init__(self, response: Any) -> None:
        self.models = _GeminiModels(response)


def _assert_canonical_envelope_v1(
    event: dict[str, Any],
    *,
    provider: str,
    event_type: str,
    endpoint: str,
    status: str,
) -> None:
    assert event["schema_version"] == "2026-02-16"
    assert event["provider"] == provider
    assert event["event_type"] == event_type
    assert event["endpoint"] == endpoint
    assert event["status"] == status
    assert isinstance(event["timestamp"], str)
    assert isinstance(event["latency_ms"], int)
    assert event["latency_ms"] >= 0
    assert isinstance(event["model"], str)

    usage = event["usage"]
    assert isinstance(usage["prompt_tokens"], int)
    assert isinstance(usage["completion_tokens"], int)
    assert isinstance(usage["total_tokens"], int)
    assert usage["prompt_tokens"] >= 0
    assert usage["completion_tokens"] >= 0
    assert usage["total_tokens"] >= 0

    tags = event["tags"]
    assert isinstance(tags["trace_id"], str)
    assert len(tags["trace_id"]) > 0
    assert isinstance(tags["span_id"], str)
    assert len(tags["span_id"]) > 0


def test_event_envelope_v1_openai_trace_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    client = track_openai(
        _OpenAIClient(_OpenAIResponse()),
        api_key="tokvera_project_key",
        feature="support_bot",
        tenant_id="acme",
        trace_id="trc_contract_1",
        run_id="run_contract_1",
        span_id="spn_contract_1",
        parent_span_id="spn_parent_1",
        conversation_id="conv_contract_1",
        step_name="draft_reply",
    )

    client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}])

    assert len(emitted) == 1
    event = emitted[0]
    _assert_canonical_envelope_v1(
        event,
        provider="openai",
        event_type="openai.request",
        endpoint="chat.completions.create",
        status="success",
    )
    assert event["tags"]["run_id"] == "run_contract_1"
    assert event["tags"]["parent_span_id"] == "spn_parent_1"
    assert event["tags"]["conversation_id"] == "conv_contract_1"
    assert event["tags"]["step_name"] == "draft_reply"


def test_event_envelope_v1_anthropic_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    client = track_anthropic(
        _AnthropicClient(_AnthropicResponse()),
        api_key="tokvera_project_key",
        feature="support_bot",
        tenant_id="acme",
    )
    client.messages.create(model="claude-3-5-sonnet-latest", messages=[{"role": "user", "content": "hi"}])

    assert len(emitted) == 1
    event = emitted[0]
    _assert_canonical_envelope_v1(
        event,
        provider="anthropic",
        event_type="anthropic.request",
        endpoint="messages.create",
        status="success",
    )
    assert event["usage"]["prompt_tokens"] == 11
    assert event["usage"]["completion_tokens"] == 9
    assert event["usage"]["total_tokens"] == 20


def test_event_envelope_v1_gemini_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    client = track_gemini(
        _GeminiClient(_GeminiResponse()),
        api_key="tokvera_project_key",
        feature="assistant",
        tenant_id="acme",
    )
    client.models.generate_content(model="gemini-2.0-flash", contents="hello")

    assert len(emitted) == 1
    event = emitted[0]
    _assert_canonical_envelope_v1(
        event,
        provider="gemini",
        event_type="gemini.request",
        endpoint="models.generate_content",
        status="success",
    )
    assert event["usage"]["prompt_tokens"] == 13
    assert event["usage"]["completion_tokens"] == 7
    assert event["usage"]["total_tokens"] == 20
