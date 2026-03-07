from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tokvera.integrations.langchain import (
    TokveraLangChainCallbackHandler,
    create_langchain_callback_handler,
)


@dataclass
class _LLMResult:
    llm_output: dict[str, Any]


def test_langchain_callback_emits_success_event(monkeypatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.integrations.langchain.ingest_event_async", fake_ingest)

    callback = create_langchain_callback_handler(
        api_key="tokvera_project_key",
        feature="agent_support",
        tenant_id="acme",
        quality_label="good",
        feedback_score=4.0,
    )

    callback.on_llm_start(
        serialized={"kwargs": {"model": "gpt-4o-mini"}},
        prompts=["hello"],
        run_id="run_100",
        metadata={"conversation_id": "conv_100", "step_name": "draft_reply"},
    )
    callback.on_llm_end(
        _LLMResult(
            llm_output={
                "token_usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 7,
                    "total_tokens": 19,
                }
            }
        ),
        run_id="run_100",
    )

    assert len(emitted) == 1
    event = emitted[0]
    assert event["provider"] == "openai"
    assert event["event_type"] == "openai.request"
    assert event["endpoint"] == "chat.completions.create"
    assert event["status"] == "success"
    assert event["usage"]["prompt_tokens"] == 12
    assert event["usage"]["completion_tokens"] == 7
    assert event["usage"]["total_tokens"] == 19
    assert event["tags"]["feature"] == "agent_support"
    assert event["tags"]["trace_id"].startswith("trc_")
    assert event["tags"]["span_id"].startswith("spn_")
    assert event["tags"]["run_id"] == "run_100"
    assert event["tags"]["conversation_id"] == "conv_100"
    assert event["tags"]["step_name"] == "draft_reply"
    assert event["tags"]["quality_label"] == "good"
    assert event["tags"]["feedback_score"] == 4.0
    assert event["evaluation"]["feedback_score"] == 4.0


def test_langchain_callback_emits_failure_event(monkeypatch) -> None:
    emitted: list[dict[str, Any]] = []

    def fake_ingest(payload: dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
        emitted.append(payload)

    monkeypatch.setattr("tokvera.integrations.langchain.ingest_event_async", fake_ingest)

    callback = TokveraLangChainCallbackHandler(
        api_key="tokvera_project_key",
        feature="agent_support",
        tenant_id="acme",
        model="claude-3-5-sonnet-latest",
    )
    callback.on_llm_start(
        serialized={"kwargs": {"model": "claude-3-5-sonnet-latest"}},
        prompts=["hello"],
        run_id="run_200",
    )
    callback.on_llm_error(RuntimeError("llm failure"), run_id="run_200")

    assert len(emitted) == 1
    event = emitted[0]
    assert event["provider"] == "anthropic"
    assert event["event_type"] == "anthropic.request"
    assert event["endpoint"] == "messages.create"
    assert event["status"] == "failure"
    assert event["usage"]["total_tokens"] == 0
    assert event["error"]["message"] == "llm failure"
    assert event["tags"]["outcome"] == "failure"
