from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..track import (
    TRACE_SCHEMA_VERSION_V2,
    TokveraTracer,
    TraceHandle,
    attach_payload,
    create_tracer,
    fail_span,
    finish_span,
    get_track_kwargs_from_trace_context,
    start_span,
    start_trace,
)


def _with_defaults(kwargs: dict[str, Any], *, step_name: str, span_kind: str) -> dict[str, Any]:
    next_kwargs = dict(kwargs)
    next_kwargs.setdefault("step_name", step_name)
    next_kwargs.setdefault("span_kind", span_kind)
    return next_kwargs


@dataclass
class TokveraRuntimeAdapter:
    runtime: str
    tracer: TokveraTracer

    def start_run(self, **kwargs: Any) -> TraceHandle:
        return start_trace(self.tracer, **_with_defaults(kwargs, step_name=f"{self.runtime}_run", span_kind="orchestrator"))

    def finish_run(self, handle: TraceHandle, **kwargs: Any) -> None:
        finish_span(handle, **kwargs)

    def fail_run(self, handle: TraceHandle, error: Any, **kwargs: Any) -> None:
        fail_span(handle, error, **kwargs)

    def start_tool(self, parent: TraceHandle, **kwargs: Any) -> TraceHandle:
        return start_span(parent, **_with_defaults(kwargs, step_name="tool_call", span_kind="tool"))

    def finish_tool(self, handle: TraceHandle, **kwargs: Any) -> None:
        finish_span(handle, **kwargs)

    def fail_tool(self, handle: TraceHandle, error: Any, **kwargs: Any) -> None:
        fail_span(handle, error, **kwargs)

    def start_model(self, parent: TraceHandle, **kwargs: Any) -> TraceHandle:
        return start_span(parent, **_with_defaults(kwargs, step_name="model_call", span_kind="model"))

    def finish_model(self, handle: TraceHandle, **kwargs: Any) -> None:
        finish_span(handle, **kwargs)

    def fail_model(self, handle: TraceHandle, error: Any, **kwargs: Any) -> None:
        fail_span(handle, error, **kwargs)

    def start_node(self, parent: TraceHandle, **kwargs: Any) -> TraceHandle:
        return start_span(parent, **_with_defaults(kwargs, step_name="graph_node", span_kind="orchestrator"))

    def finish_node(self, handle: TraceHandle, **kwargs: Any) -> None:
        finish_span(handle, **kwargs)

    def fail_node(self, handle: TraceHandle, error: Any, **kwargs: Any) -> None:
        fail_span(handle, error, **kwargs)

    def start_branch(self, parent: TraceHandle, **kwargs: Any) -> TraceHandle:
        return start_span(parent, **_with_defaults(kwargs, step_name="branch_decision", span_kind="orchestrator"))

    def finish_branch(self, handle: TraceHandle, **kwargs: Any) -> None:
        finish_span(handle, **kwargs)

    def fail_branch(self, handle: TraceHandle, error: Any, **kwargs: Any) -> None:
        fail_span(handle, error, **kwargs)

    def attach_payload(self, handle: TraceHandle, payload: Any) -> TraceHandle:
        return attach_payload(handle, payload)

    def get_track_kwargs_from_trace_context(self, handle: TraceHandle, **kwargs: Any) -> dict[str, Any]:
        return get_track_kwargs_from_trace_context(handle, **kwargs)


@dataclass
class TokveraClaudeAgentSDKTracer(TokveraRuntimeAdapter):
    def start_agent(self, **kwargs: Any) -> TraceHandle:
        return self.start_run(**_with_defaults(kwargs, step_name="claude_agent_run", span_kind="orchestrator"))


@dataclass
class TokveraGoogleADKTracer(TokveraRuntimeAdapter):
    def start_agent(self, **kwargs: Any) -> TraceHandle:
        return self.start_run(**_with_defaults(kwargs, step_name="google_adk_run", span_kind="orchestrator"))


@dataclass
class TokveraLangGraphTracer(TokveraRuntimeAdapter):
    def start_graph(self, **kwargs: Any) -> TraceHandle:
        return self.start_run(**_with_defaults(kwargs, step_name="langgraph_run", span_kind="orchestrator"))


@dataclass
class TokveraInstructorTracer(TokveraRuntimeAdapter):
    def start_extraction(self, **kwargs: Any) -> TraceHandle:
        return self.start_run(**_with_defaults(kwargs, step_name="instructor_extract", span_kind="orchestrator"))

    def start_validation(self, parent: TraceHandle, **kwargs: Any) -> TraceHandle:
        return self.start_branch(parent, **_with_defaults(kwargs, step_name="validation_retry", span_kind="guardrail"))


@dataclass
class TokveraPydanticAITracer(TokveraRuntimeAdapter):
    def start_agent(self, **kwargs: Any) -> TraceHandle:
        return self.start_run(**_with_defaults(kwargs, step_name="pydanticai_run", span_kind="orchestrator"))

    def start_validation(self, parent: TraceHandle, **kwargs: Any) -> TraceHandle:
        return self.start_branch(parent, **_with_defaults(kwargs, step_name="pydantic_validation", span_kind="guardrail"))


@dataclass
class TokveraCrewAITracer(TokveraRuntimeAdapter):
    def start_crew(self, **kwargs: Any) -> TraceHandle:
        return self.start_run(**_with_defaults(kwargs, step_name="crew_run", span_kind="orchestrator"))


def configure_claude_agent_sdk(**kwargs: Any) -> TokveraClaudeAgentSDKTracer:
    kwargs.setdefault("schema_version", TRACE_SCHEMA_VERSION_V2)
    return TokveraClaudeAgentSDKTracer(runtime="claude_agent_sdk", tracer=create_tracer(**kwargs))


def configure_google_adk(**kwargs: Any) -> TokveraGoogleADKTracer:
    kwargs.setdefault("schema_version", TRACE_SCHEMA_VERSION_V2)
    return TokveraGoogleADKTracer(runtime="google_adk", tracer=create_tracer(**kwargs))


def create_langgraph_tracer(**kwargs: Any) -> TokveraLangGraphTracer:
    kwargs.setdefault("schema_version", TRACE_SCHEMA_VERSION_V2)
    return TokveraLangGraphTracer(runtime="langgraph", tracer=create_tracer(**kwargs))


def create_instructor_tracer(**kwargs: Any) -> TokveraInstructorTracer:
    kwargs.setdefault("schema_version", TRACE_SCHEMA_VERSION_V2)
    return TokveraInstructorTracer(runtime="instructor", tracer=create_tracer(**kwargs))


def create_pydanticai_tracer(**kwargs: Any) -> TokveraPydanticAITracer:
    kwargs.setdefault("schema_version", TRACE_SCHEMA_VERSION_V2)
    return TokveraPydanticAITracer(runtime="pydanticai", tracer=create_tracer(**kwargs))


def create_crewai_tracer(**kwargs: Any) -> TokveraCrewAITracer:
    kwargs.setdefault("schema_version", TRACE_SCHEMA_VERSION_V2)
    return TokveraCrewAITracer(runtime="crewai", tracer=create_tracer(**kwargs))
