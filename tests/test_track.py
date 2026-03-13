from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from tokvera.track import track_anthropic, track_gemini, track_openai


@dataclass
class _Usage:
    prompt_tokens: int = 10
    completion_tokens: int = 5
    total_tokens: int = 15


@dataclass
class _Response:
    model: str = "gpt-4o-mini"
    usage: _Usage = field(default_factory=_Usage)


class _Completions:
    def __init__(self, response: Any) -> None:
        self._response = response

    def create(self, *args: Any, **kwargs: Any) -> Any:
        return self._response


class _Chat:
    def __init__(self, response: Any) -> None:
        self.completions = _Completions(response)


class _Responses:
    def __init__(self, response: Any) -> None:
        self._response = response

    def create(self, *args: Any, **kwargs: Any) -> Any:
        return self._response


class _OpenAIClient:
    def __init__(self, response: Any) -> None:
        self.chat = _Chat(response)
        self.responses = _Responses(response)


@dataclass
class _AnthropicUsage:
    input_tokens: int = 11
    output_tokens: int = 7


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
class _GeminiUsageMetadata:
    prompt_token_count: int = 9
    candidates_token_count: int = 6
    total_token_count: int = 15


@dataclass
class _GeminiResponse:
    model_version: str = "gemini-2.0-flash"
    usage_metadata: _GeminiUsageMetadata = field(default_factory=_GeminiUsageMetadata)


class _GeminiModels:
    def __init__(self, response: Any) -> None:
        self._response = response

    def generate_content(self, *args: Any, **kwargs: Any) -> Any:
        return self._response


class _GeminiClient:
    def __init__(self, response: Any) -> None:
        self.models = _GeminiModels(response)


def test_chat_wrapper_returns_original_object_and_triggers_ingest(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _Response()
    openai_client = _OpenAIClient(response)

    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    client = track_openai(
        openai_client,
        api_key="tokvera_project_key",
        feature="support_bot",
        tenant_id="acme",
        attempt_type="regenerate",
        trace_id="trace_support_123",
        run_id="run_support_123",
        conversation_id="conv_88",
        parent_span_id="spn_parent_01",
        step_name="draft_reply",
        outcome="success",
        retry_reason="none",
        fallback_reason="none",
        quality_label="good",
        feedback_score=4.5,
        plan="pro",
        environment="production",
        template_id="support_v3",
        capture_content=False,
    )

    result = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}])

    assert result is response
    assert len(emitted) == 1
    assert emitted[0]["schema_version"] == "2026-02-16"
    assert emitted[0]["provider"] == "openai"
    assert emitted[0]["event_type"] == "openai.request"
    assert emitted[0]["endpoint"] == "chat.completions.create"
    assert emitted[0]["status"] == "success"
    assert emitted[0]["model"] == "gpt-4o-mini"
    assert emitted[0]["usage"]["prompt_tokens"] == 10
    assert emitted[0]["usage"]["completion_tokens"] == 5
    assert emitted[0]["usage"]["total_tokens"] == 15
    assert emitted[0]["tags"]["feature"] == "support_bot"
    assert emitted[0]["tags"]["tenant_id"] == "acme"
    assert emitted[0]["tags"]["attempt_type"] == "regenerate"
    assert emitted[0]["tags"]["trace_id"] == "trace_support_123"
    assert emitted[0]["tags"]["run_id"] == "run_support_123"
    assert emitted[0]["tags"]["conversation_id"] == "conv_88"
    assert emitted[0]["tags"]["parent_span_id"] == "spn_parent_01"
    assert emitted[0]["tags"]["step_name"] == "draft_reply"
    assert emitted[0]["tags"]["outcome"] == "success"
    assert emitted[0]["tags"]["retry_reason"] == "none"
    assert emitted[0]["tags"]["fallback_reason"] == "none"
    assert emitted[0]["tags"]["quality_label"] == "good"
    assert emitted[0]["tags"]["feedback_score"] == 4.5
    assert emitted[0]["evaluation"]["outcome"] == "success"
    assert emitted[0]["evaluation"]["feedback_score"] == 4.5
    assert isinstance(emitted[0]["tags"]["span_id"], str)
    assert len(emitted[0]["tags"]["span_id"]) > 0


def test_responses_wrapper_returns_original_object(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _Response()
    openai_client = _OpenAIClient(response)

    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    client = track_openai(
        openai_client,
        api_key="tokvera_project_key",
        feature="assistant",
        tenant_id="tenant-1",
    )

    result = client.responses.create(model="gpt-4o-mini", input="hello")

    assert result is response
    assert len(emitted) == 1
    assert emitted[0]["endpoint"] == "responses.create"
    assert emitted[0]["status"] == "success"
    assert isinstance(emitted[0]["tags"]["trace_id"], str)
    assert isinstance(emitted[0]["tags"]["span_id"], str)


def test_emit_lifecycle_events_sends_in_progress_before_success(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _Response()
    openai_client = _OpenAIClient(response)

    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    client = track_openai(
        openai_client,
        api_key="tokvera_project_key",
        feature="support_bot",
        tenant_id="acme",
        emit_lifecycle_events=True,
        capture_content=True,
    )

    result = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}])

    assert result is response
    assert len(emitted) == 2
    assert emitted[0]["status"] == "in_progress"
    assert emitted[0]["tags"]["run_id"].startswith("run_")
    assert emitted[0]["tags"]["trace_id"].startswith("trc_")
    assert emitted[0]["tags"]["outcome"] is None
    assert emitted[0]["payload_blocks"]
    assert emitted[1]["status"] == "success"
    assert emitted[1]["tags"]["run_id"] == emitted[0]["tags"]["run_id"]
    assert emitted[1]["tags"]["trace_id"] == emitted[0]["tags"]["trace_id"]
    assert emitted[1]["usage"]["total_tokens"] == 15


def test_ingestion_failure_does_not_break_user_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _Response()
    openai_client = _OpenAIClient(response)

    def failing_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        raise RuntimeError("ingestion failed")

    monkeypatch.setattr("tokvera.track.ingest_event_async", failing_ingest)

    client = track_openai(
        openai_client,
        api_key="tokvera_project_key",
        feature="support_bot",
        tenant_id="acme",
    )

    result = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}])

    assert result is response


def test_failure_in_openai_call_is_re_raised_and_still_attempts_ingest(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingCompletions:
        def create(self, *args: Any, **kwargs: Any) -> Any:
            raise ValueError("openai failure")

    class _FailingChat:
        def __init__(self) -> None:
            self.completions = _FailingCompletions()

    class _Client:
        def __init__(self) -> None:
            self.chat = _FailingChat()
            self.responses = _Responses(_Response())

    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    client = track_openai(
        _Client(),
        api_key="tokvera_project_key",
        feature="support_bot",
        tenant_id="acme",
    )

    with pytest.raises(ValueError, match="openai failure"):
        client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}])

    assert len(emitted) == 1
    assert emitted[0]["endpoint"] == "chat.completions.create"
    assert emitted[0]["status"] == "failure"
    assert emitted[0]["error"]["type"] == "ValueError"
    assert emitted[0]["error"]["message"] == "openai failure"


def test_anthropic_wrapper_emits_anthropic_event(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _AnthropicResponse()
    anthropic_client = _AnthropicClient(response)

    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    client = track_anthropic(
        anthropic_client,
        api_key="tokvera_project_key",
        feature="support_bot",
        tenant_id="acme",
    )

    result = client.messages.create(model="claude-3-5-sonnet-latest", messages=[{"role": "user", "content": "hi"}])

    assert result is response
    assert len(emitted) == 1
    assert emitted[0]["provider"] == "anthropic"
    assert emitted[0]["event_type"] == "anthropic.request"
    assert emitted[0]["endpoint"] == "messages.create"
    assert emitted[0]["usage"]["prompt_tokens"] == 11
    assert emitted[0]["usage"]["completion_tokens"] == 7
    assert emitted[0]["usage"]["total_tokens"] == 18


def test_gemini_wrapper_emits_gemini_event(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _GeminiResponse()
    gemini_client = _GeminiClient(response)

    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    client = track_gemini(
        gemini_client,
        api_key="tokvera_project_key",
        feature="assistant",
        tenant_id="acme",
    )

    result = client.models.generate_content(model="gemini-2.0-flash", contents="hello")

    assert result is response
    assert len(emitted) == 1
    assert emitted[0]["provider"] == "gemini"
    assert emitted[0]["event_type"] == "gemini.request"
    assert emitted[0]["endpoint"] == "models.generate_content"
    assert emitted[0]["usage"]["prompt_tokens"] == 9
    assert emitted[0]["usage"]["completion_tokens"] == 6
    assert emitted[0]["usage"]["total_tokens"] == 15
