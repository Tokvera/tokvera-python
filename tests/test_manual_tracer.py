from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tokvera import (
    TokveraOTelSpanExporter,
    create_tracer,
    finish_span,
    get_track_kwargs_from_trace_context,
    start_span,
    start_trace,
    track_mistral,
)


@dataclass
class _MistralUsage:
    prompt_tokens: int = 10
    completion_tokens: int = 4
    total_tokens: int = 14


@dataclass
class _MistralResponse:
    model: str = "mistral-small-latest"
    usage: _MistralUsage = field(default_factory=_MistralUsage)
    choices: list[dict[str, Any]] = field(
        default_factory=lambda: [{"message": {"content": "Hello"}}]
    )


class _MistralChat:
    def __init__(self, response: Any) -> None:
        self._response = response

    def complete(self, *args: Any, **kwargs: Any) -> Any:
        return self._response


class _MistralClient:
    def __init__(self, response: Any) -> None:
        self.chat = _MistralChat(response)


def test_manual_tracer_creates_root_and_child_spans(monkeypatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    tracer = create_tracer(
        api_key="tokvera_project_key",
        feature="support_router",
        tenant_id="acme",
        emit_lifecycle_events=True,
    )

    root = start_trace(tracer, step_name="handle_ticket", model="custom-router", span_kind="orchestrator")
    child = start_span(root, step_name="draft_reply", span_kind="tool", tool_name="draft_reply")
    child_kwargs = get_track_kwargs_from_trace_context(child, step_name="draft_reply_model", span_kind="model")

    finish_span(child, response={"ok": True})
    finish_span(root, response={"completed": True})

    assert root.trace_id.startswith("trc_")
    assert child.trace_id == root.trace_id
    assert child.run_id == root.run_id
    assert child.parent_span_id == root.span_id
    assert child_kwargs["trace_id"] == root.trace_id
    assert child_kwargs["run_id"] == root.run_id
    assert child_kwargs["parent_span_id"] == child.span_id
    assert child_kwargs["span_id"].startswith("spn_")
    assert emitted[0]["provider"] == "tokvera"
    assert emitted[0]["event_type"] == "tokvera.trace"
    assert emitted[0]["endpoint"] == "manual.trace"
    assert emitted[1]["endpoint"] == "manual.span"
    assert emitted[2]["status"] == "success"


def test_track_mistral_emits_canonical_event(monkeypatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    client = track_mistral(
        _MistralClient(_MistralResponse()),
        api_key="tokvera_project_key",
        feature="draft_reply",
        tenant_id="acme",
        emit_lifecycle_events=True,
        capture_content=True,
    )

    client.chat.complete(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": "Summarize this request."}],
    )

    assert len(emitted) == 2
    assert emitted[1]["provider"] == "mistral"
    assert emitted[1]["event_type"] == "mistral.request"
    assert emitted[1]["endpoint"] == "chat.complete"
    assert emitted[1]["usage"]["total_tokens"] == 14


def test_otel_exporter_maps_spans_to_tokvera_events(monkeypatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    exporter = TokveraOTelSpanExporter(
        api_key="tokvera_project_key",
        feature="otel_bridge",
        tenant_id="acme",
    )

    class _Status:
        is_ok = True

    class _Context:
        trace_id = "trc_otel_1"
        span_id = "spn_otel_1"

    class _Span:
        name = "planner"
        start_time = 100.0
        end_time = 100.2
        attributes = {
            "tokvera.provider": "openai",
            "tokvera.step_name": "planner",
            "gen_ai.response.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 9,
            "gen_ai.usage.output_tokens": 6,
        }
        resource = type("Resource", (), {"attributes": {"service.name": "planner"}})()
        status = _Status()

        def get_span_context(self):
            return _Context()

    exporter.export([_Span()])

    assert emitted[0]["tags"]["trace_id"] == "trc_otel_1"
    assert emitted[0]["provider"] == "openai"
    assert emitted[0]["usage"]["prompt_tokens"] == 9
    assert emitted[0]["usage"]["completion_tokens"] == 6
