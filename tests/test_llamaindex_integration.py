from __future__ import annotations

from tokvera.integrations.llamaindex import (
    TokveraLlamaIndexCallbackHandler,
    create_llamaindex_callback_handler,
)


def test_llamaindex_callback_emits_success_event(monkeypatch) -> None:
    emitted: list[dict] = []

    def fake_ingest(payload: dict, *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.integrations.llamaindex.ingest_event_async", fake_ingest)

    callback = create_llamaindex_callback_handler(
        api_key="tokvera_project_key",
        feature="agent_support",
        tenant_id="acme",
        quality_label="good",
        feedback_score=5,
    )

    event_id = callback.on_event_start(
        event_type="LLM",
        payload={"model": "gpt-4o-mini"},
        event_id="evt_100",
    )
    callback.on_event_end(
        event_type="LLM",
        payload={
            "prompt_tokens": 9,
            "completion_tokens": 6,
            "total_tokens": 15,
        },
        event_id=event_id,
    )

    assert len(emitted) == 1
    event = emitted[0]
    assert event["provider"] == "openai"
    assert event["event_type"] == "openai.request"
    assert event["endpoint"] == "chat.completions.create"
    assert event["status"] == "success"
    assert event["usage"]["prompt_tokens"] == 9
    assert event["usage"]["completion_tokens"] == 6
    assert event["usage"]["total_tokens"] == 15
    assert event["tags"]["feature"] == "agent_support"
    assert event["tags"]["trace_id"].startswith("trc_")
    assert event["tags"]["span_id"].startswith("spn_")
    assert event["tags"]["quality_label"] == "good"
    assert event["evaluation"]["feedback_score"] == 5.0


def test_llamaindex_callback_emits_failure_event(monkeypatch) -> None:
    emitted: list[dict] = []

    def fake_ingest(payload: dict, *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.integrations.llamaindex.ingest_event_async", fake_ingest)

    callback = TokveraLlamaIndexCallbackHandler(
        api_key="tokvera_project_key",
        feature="agent_support",
        tenant_id="acme",
        model="claude-3-5-sonnet-latest",
    )

    callback.on_event_start(
        event_type="LLM",
        payload={"model": "claude-3-5-sonnet-latest"},
        event_id="evt_200",
    )
    callback.on_event_error(
        event_type="LLM",
        error=RuntimeError("llm failure"),
        event_id="evt_200",
    )

    assert len(emitted) == 1
    event = emitted[0]
    assert event["provider"] == "anthropic"
    assert event["event_type"] == "anthropic.request"
    assert event["endpoint"] == "messages.create"
    assert event["status"] == "failure"
    assert event["usage"]["total_tokens"] == 0
    assert event["error"]["message"] == "llm failure"
    assert event["tags"]["outcome"] == "failure"


def test_llamaindex_callback_emits_v2_trace_fields(monkeypatch) -> None:
    emitted: list[dict] = []

    def fake_ingest(payload: dict, *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.integrations.llamaindex.ingest_event_async", fake_ingest)

    callback = create_llamaindex_callback_handler(
        api_key="tokvera_project_key",
        feature="agent_support",
        tenant_id="acme",
        schema_version="2026-04-01",
        span_kind="tool",
        tool_name="search_docs",
        payload_refs=["ref_123"],
        payload_blocks=[{"payload_type": "context", "content": "cached policy"}],
        metrics={"estimated_cost_usd": 0.0002},
        decision={"routing_reason": "budget_route", "route": "openai:gpt-4o-mini"},
    )

    event_id = callback.on_event_start(
        event_type="LLM",
        payload={"model": "gpt-4o-mini"},
        event_id="evt_300",
    )
    callback.on_event_end(
        event_type="LLM",
        payload={
            "prompt_tokens": 4,
            "completion_tokens": 2,
            "total_tokens": 6,
        },
        event_id=event_id,
    )

    assert len(emitted) == 1
    event = emitted[0]
    assert event["schema_version"] == "2026-04-01"
    assert event["span_kind"] == "tool"
    assert event["tool_name"] == "search_docs"
    assert event["payload_refs"] == ["ref_123"]
    assert event["metrics"]["cost_usd"] == 0.0002
    assert event["decision"]["routing_reason"] == "budget_route"
    assert event["decision"]["route"] == "openai:gpt-4o-mini"
    assert isinstance(event["payload_blocks"], list)
    assert len(event["payload_blocks"]) >= 1
