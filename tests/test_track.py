from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from tokvera.track import track_openai


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
        plan="pro",
        environment="production",
        template_id="support_v3",
        capture_content=False,
    )

    result = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}])

    assert result is response
    assert len(emitted) == 1
    assert emitted[0]["provider"] == "openai"
    assert emitted[0]["status"] == "success"
    assert emitted[0]["model"] == "gpt-4o-mini"
    assert emitted[0]["prompt_tokens"] == 10
    assert emitted[0]["completion_tokens"] == 5
    assert emitted[0]["total_tokens"] == 15


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
    assert emitted[0]["status"] == "success"


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
    assert emitted[0]["status"] == "failure"
