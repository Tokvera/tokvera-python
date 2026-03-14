from __future__ import annotations

from typing import Any, Callable

import pytest

from tokvera import (
    configure_claude_agent_sdk,
    configure_google_adk,
    create_crewai_tracer,
    create_instructor_tracer,
    create_langgraph_tracer,
    create_pydanticai_tracer,
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
