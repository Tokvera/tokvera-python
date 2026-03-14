from __future__ import annotations

from typing import Any, Callable

import pytest

from tokvera import (
    create_autogen_tracer,
    configure_claude_agent_sdk,
    configure_google_adk,
    create_crewai_tracer,
    create_instructor_tracer,
    create_langgraph_tracer,
    create_livekit_tracer,
    create_mastra_tracer,
    create_openai_compatible_gateway_tracer,
    create_pipecat_tracer,
    create_pydanticai_tracer,
    create_temporal_tracer,
)


@pytest.mark.parametrize(
    ("factory", "runtime_name"),
    [
        (configure_claude_agent_sdk, "claude_agent_sdk"),
        (configure_google_adk, "google_adk"),
        (create_instructor_tracer, "instructor"),
        (create_pydanticai_tracer, "pydanticai"),
        (create_crewai_tracer, "crewai"),
    ],
)
def test_runtime_adapters_emit_root_and_child_events(
    monkeypatch: pytest.MonkeyPatch,
    factory: Callable[..., Any],
    runtime_name: str,
) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    adapter = factory(
        api_key="tokvera_project_key",
        feature=runtime_name,
        tenant_id="acme",
        emit_lifecycle_events=True,
    )

    root = adapter.start_run(step_name=f"{runtime_name}_run")
    child = adapter.start_tool(root, step_name="lookup_context", tool_name="lookup_context")
    adapter.finish_tool(child, response={"documents": 3})
    adapter.finish_run(root, response={"status": "completed"})

    assert len(emitted) == 4
    assert emitted[0]["status"] == "in_progress"
    assert emitted[0]["tags"]["trace_id"] == root.trace_id
    assert emitted[2]["tags"]["parent_span_id"] == root.span_id
    assert emitted[2]["span_kind"] == "tool"
    assert emitted[3]["tags"]["trace_id"] == root.trace_id


def test_langgraph_tracer_emits_node_and_branch_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    tracer = create_langgraph_tracer(
        api_key="tokvera_project_key",
        feature="langgraph_workflow",
        tenant_id="acme",
        emit_lifecycle_events=True,
        schema_version="2026-04-01",
    )

    graph = tracer.start_graph(step_name="customer_journey_graph")
    node = tracer.start_node(graph, step_name="planner")
    tracer.finish_node(node, response={"next": "kb_search"})
    branch = tracer.start_branch(
        graph,
        step_name="route_branch",
        decision={"routing_reason": "policy_lookup", "route": "kb_search"},
    )
    tracer.finish_branch(branch, response={"route": "kb_search"})
    tracer.finish_run(graph, response={"status": "completed"})

    assert len(emitted) == 6
    assert emitted[2]["tags"]["step_name"] == "planner"
    assert emitted[4]["tags"]["step_name"] == "route_branch"
    assert emitted[4]["decision"]["route"] == "kb_search"


@pytest.mark.parametrize(
    ("factory", "runtime_name", "start_root_name", "start_child_name", "expected_step_name", "expected_span_kind", "child_kwargs"),
    [
        (create_autogen_tracer, "autogen", "start_conversation", "start_agent", "planner_agent", "orchestrator", {}),
        (create_mastra_tracer, "mastra", "start_workflow", "start_step", "search_docs", "orchestrator", {}),
        (create_temporal_tracer, "temporal", "start_workflow", "start_activity", "lookup_account", "tool", {"tool_name": "lookup_account"}),
        (
            create_pipecat_tracer,
            "pipecat",
            "start_turn",
            "start_transcription",
            "speech_to_text",
            "model",
            {"provider": "openai", "model": "gpt-4o-mini-transcribe"},
        ),
        (
            create_livekit_tracer,
            "livekit",
            "start_session",
            "start_turn",
            "voice_turn",
            "model",
            {"provider": "openai", "model": "gpt-4o-realtime-preview"},
        ),
    ],
)
def test_wave2_runtime_helpers_emit_root_and_child_events(
    monkeypatch: pytest.MonkeyPatch,
    factory: Callable[..., Any],
    runtime_name: str,
    start_root_name: str,
    start_child_name: str,
    expected_step_name: str,
    expected_span_kind: str,
    child_kwargs: dict[str, Any],
) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    adapter = factory(
        api_key="tokvera_project_key",
        feature=runtime_name,
        tenant_id="acme",
        emit_lifecycle_events=True,
    )

    root = getattr(adapter, start_root_name)(step_name=f"{runtime_name}_root")
    child = getattr(adapter, start_child_name)(root, step_name=expected_step_name, **child_kwargs)

    if expected_span_kind == "tool":
        adapter.finish_tool(child, response={"status": "ok"})
    elif expected_span_kind == "model":
        adapter.finish_model(child, response={"status": "ok"})
    else:
        adapter.finish_node(child, response={"status": "ok"})

    adapter.finish_run(root, response={"status": "completed"})

    assert len(emitted) == 4
    assert emitted[0]["status"] == "in_progress"
    assert emitted[2]["tags"]["trace_id"] == root.trace_id
    assert emitted[2]["tags"]["parent_span_id"] == root.span_id
    assert emitted[2]["tags"]["step_name"] == expected_step_name
    assert emitted[2]["span_kind"] == expected_span_kind


def test_openai_compatible_gateway_emits_downstream_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.track.ingest_event_async", fake_ingest)

    tracer = create_openai_compatible_gateway_tracer(
        api_key="tokvera_project_key",
        feature="gateway_router",
        tenant_id="acme",
        emit_lifecycle_events=True,
    )

    request = tracer.start_request(step_name="gateway_request", model="router")
    downstream = tracer.start_downstream(
        request,
        step_name="downstream_provider_call",
        provider="openai",
        model="gpt-4o-mini",
    )
    tracer.finish_model(downstream, response={"output_text": "ok"}, usage={"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10})
    fallback = tracer.start_fallback(
        request,
        step_name="fallback_route",
        decision={"fallback_reason": "rate_limit", "route": "anthropic"},
    )
    tracer.finish_branch(fallback, response={"route": "anthropic"})
    tracer.finish_run(request, response={"status": "completed"})

    assert len(emitted) == 6
    assert emitted[2]["provider"] == "openai"
    assert emitted[2]["tags"]["parent_span_id"] == request.span_id
    assert emitted[2]["span_kind"] == "model"
    assert emitted[2]["usage"]["total_tokens"] == 10
    assert emitted[4]["decision"]["route"] == "anthropic"
