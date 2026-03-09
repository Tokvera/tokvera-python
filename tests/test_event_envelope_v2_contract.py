from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from tokvera.track import track_openai

ALLOWED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "event_type",
    "provider",
    "endpoint",
    "status",
    "timestamp",
    "latency_ms",
    "model",
    "usage",
    "tags",
    "prompt_hash",
    "response_hash",
    "error",
    "evaluation",
    "span_kind",
    "tool_name",
    "payload_refs",
    "payload_blocks",
    "metrics",
    "decision",
}
ALLOWED_METRIC_FIELDS = {"prompt_tokens", "completion_tokens", "total_tokens", "latency_ms", "cost_usd"}
ALLOWED_DECISION_FIELDS = {"outcome", "retry_reason", "fallback_reason", "routing_reason", "route"}
ALLOWED_PAYLOAD_TYPES = {"prompt_input", "tool_input", "tool_output", "model_output", "context", "other"}


@dataclass
class _Usage:
    prompt_tokens: int = 10
    completion_tokens: int = 6
    total_tokens: int = 16


@dataclass
class _Message:
    content: str = "sample response"


@dataclass
class _Choice:
    message: _Message = field(default_factory=_Message)


@dataclass
class _Response:
    model: str = "gpt-4o-mini"
    usage: _Usage = field(default_factory=_Usage)
    choices: list[_Choice] = field(default_factory=lambda: [_Choice()])


class _Completions:
    def __init__(self, response: Any) -> None:
        self._response = response

    def create(self, *args: Any, **kwargs: Any) -> Any:
        return self._response


class _Chat:
    def __init__(self, response: Any) -> None:
        self.completions = _Completions(response)


class _Responses:
    def __init__(self) -> None:
        pass

    def create(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError


class _OpenAIClient:
    def __init__(self, response: Any) -> None:
        self.chat = _Chat(response)
        self.responses = _Responses()


def test_event_envelope_v2_openai_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    client = track_openai(
        _OpenAIClient(_Response()),
        api_key="tokvera_project_key",
        feature="assistant",
        tenant_id="acme",
        schema_version="2026-04-01",
        span_kind="tool",
        tool_name="search_docs",
        payload_refs=["ref_123"],
        payload_blocks=[{"payload_type": "context", "content": "tenant policy excerpt"}],
        metrics={"estimated_cost_usd": 0.00042},
        decision={"routing_reason": "budget_route", "route": "gpt-4o-mini"},
        capture_content=True,
    )

    client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "hello"}])

    assert len(emitted) == 1
    event = emitted[0]
    assert event["schema_version"] == "2026-04-01"
    assert set(event.keys()).issubset(ALLOWED_TOP_LEVEL_FIELDS)

    assert event["span_kind"] == "tool"
    assert event["tool_name"] == "search_docs"
    assert event["payload_refs"] == ["ref_123"]
    assert isinstance(event["payload_blocks"], list)
    assert len(event["payload_blocks"]) >= 2
    for block in event["payload_blocks"]:
        assert block["payload_type"] in ALLOWED_PAYLOAD_TYPES
        assert isinstance(block["content"], str)
        assert len(block["content"]) > 0

    assert isinstance(event["metrics"], dict)
    assert set(event["metrics"].keys()).issubset(ALLOWED_METRIC_FIELDS)
    assert event["metrics"]["cost_usd"] == 0.00042

    assert isinstance(event["decision"], dict)
    assert set(event["decision"].keys()).issubset(ALLOWED_DECISION_FIELDS)
    assert event["decision"]["routing_reason"] == "budget_route"
    assert event["decision"]["route"] == "gpt-4o-mini"

    assert isinstance(event.get("prompt_hash"), str)
    assert isinstance(event.get("response_hash"), str)


def test_event_envelope_v2_with_routing_only_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    client = track_openai(
        _OpenAIClient(_Response()),
        api_key="tokvera_project_key",
        feature="assistant",
        tenant_id="acme",
        routing_reason="cost_policy",
        route="openai:gpt-4o-mini",
    )

    client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "hello"}])

    assert len(emitted) == 1
    event = emitted[0]
    assert event["schema_version"] == "2026-04-01"
    assert event["decision"]["routing_reason"] == "cost_policy"
    assert event["decision"]["route"] == "openai:gpt-4o-mini"
