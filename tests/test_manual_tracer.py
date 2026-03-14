from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tokvera import (
    TokveraOTelSpanExporter,
    create_openai_compatible_gateway_tracer,
    create_tracer,
    finish_span,
    get_track_kwargs_from_trace_context,
    start_span,
    start_trace,
    track_openai,
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


@dataclass
class _OpenAIUsage:
    prompt_tokens: int = 6
    completion_tokens: int = 4
    total_tokens: int = 10


@dataclass
class _OpenAIResponse:
    model: str = "gpt-4o-mini"
    usage: _OpenAIUsage = field(default_factory=_OpenAIUsage)


class _Responses:
    def __init__(self, response: Any) -> None:
        self._response = response

    def create(self, *args: Any, **kwargs: Any) -> Any:
        return self._response


class _OpenAIClient:
    def __init__(self, response: Any) -> None:
        self.chat = type("Chat", (), {"completions": type("Completions", (), {"create": lambda *args, **kwargs: response})()})()
        self.responses = _Responses(response)


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


def test_manual_tracer_composes_with_openai_wrapper_without_duplicate_status_events(monkeypatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    tracer = create_tracer(
        api_key="tokvera_project_key",
        feature="mixed_manual_openai",
        tenant_id="acme",
        emit_lifecycle_events=True,
        capture_content=True,
    )

    root = start_trace(tracer, step_name="gateway_request", model="router", span_kind="orchestrator")
    downstream = start_span(root, step_name="downstream_provider_call", span_kind="model", provider="tokvera", model="provider-router")
    client = track_openai(
        _OpenAIClient(_OpenAIResponse()),
        **get_track_kwargs_from_trace_context(
            downstream,
            step_name="downstream_provider_call",
            span_kind="model",
            provider="openai",
            model="gpt-4o-mini",
            emit_lifecycle_events=True,
            capture_content=True,
        ),
    )

    client.responses.create(model="gpt-4o-mini", input="Return a short answer.")
    finish_span(downstream, response={"status": "completed"})
    finish_span(root, response={"status": "completed"})

    assert len(emitted) == 6
    keys = {f"{event['tags']['trace_id']}:{event['tags']['span_id']}:{event['status']}" for event in emitted}
    assert len(keys) == len(emitted)
    span_ids = {event["tags"]["span_id"] for event in emitted}
    assert len(span_ids) == 3
    provider_terminal = next(event for event in emitted if event["provider"] == "openai" and event["status"] == "success")
    assert provider_terminal["tags"]["parent_span_id"] == downstream.span_id
    assert provider_terminal["tags"]["trace_id"] == root.trace_id


def test_gateway_tracer_composes_with_openai_wrapper_and_fallback_without_duplicates(monkeypatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    tracer = create_openai_compatible_gateway_tracer(
        api_key="tokvera_project_key",
        feature="gateway_composition",
        tenant_id="acme",
        emit_lifecycle_events=True,
        capture_content=True,
    )

    request = tracer.start_request(step_name="gateway_request", model="router")
    downstream = tracer.start_downstream(
        request,
        step_name="downstream_provider_call",
        provider="tokvera",
        model="provider-router",
    )
    client = track_openai(
        _OpenAIClient(_OpenAIResponse()),
        **tracer.get_track_kwargs_from_trace_context(
            downstream,
            step_name="downstream_provider_call",
            span_kind="model",
            provider="openai",
            model="gpt-4o-mini",
            emit_lifecycle_events=True,
        ),
    )

    client.responses.create(model="gpt-4o-mini", input="Return a short answer.")
    tracer.finish_model(downstream, response={"output_text": "ok"})
    fallback = tracer.start_fallback(
        request,
        step_name="fallback_route",
        decision={"fallback_reason": "rate_limit", "route": "anthropic"},
    )
    tracer.finish_branch(fallback, response={"route": "anthropic"})
    tracer.finish_run(request, response={"status": "completed"})

    keys = {f"{event['tags']['trace_id']}:{event['tags']['span_id']}:{event['status']}" for event in emitted}
    assert len(keys) == len(emitted)
    trace_ids = {event["tags"]["trace_id"] for event in emitted}
    assert len(trace_ids) == 1
    fallback_terminal = next(
        event for event in emitted if event["tags"]["step_name"] == "fallback_route" and event["status"] == "success"
    )
    assert fallback_terminal["decision"]["route"] == "anthropic"
