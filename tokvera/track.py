from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, replace
from typing import Any, Callable, Optional, Sequence

from .ingest import ingest_event_async
from .types import (
    AnalyticsEvent,
    EventError,
    TraceDecision,
    TraceMetrics,
    TracePayloadBlock,
    TrackingContext,
    UsageMetrics,
)

TRACE_SCHEMA_VERSION_V1 = "2026-02-16"
TRACE_SCHEMA_VERSION_V2 = "2026-04-01"
ALLOWED_SPAN_KINDS = {"model", "tool", "orchestrator", "retrieval", "guardrail"}
ALLOWED_PAYLOAD_TYPES = {"prompt_input", "tool_input", "tool_output", "model_output", "context", "other"}


@dataclass
class TraceHandle:
    trace_id: str
    run_id: str
    span_id: str
    started_at: float
    provider: str
    event_type: str
    endpoint: str
    context: TrackingContext
    parent_span_id: Optional[str] = None
    model: Optional[str] = None


class TokveraTracer:
    def __init__(self, context: TrackingContext) -> None:
        self.context = context

    def start_trace(self, **kwargs: Any) -> TraceHandle:
        return start_trace(self, **kwargs)

    def start_span(self, parent: TraceHandle, **kwargs: Any) -> TraceHandle:
        return start_span(parent, **kwargs)

    def finish_span(self, handle: TraceHandle, **kwargs: Any) -> None:
        finish_span(handle, **kwargs)

    def fail_span(self, handle: TraceHandle, error: Any, **kwargs: Any) -> None:
        fail_span(handle, error, **kwargs)

    def attach_payload(self, handle: TraceHandle, payload: Any) -> TraceHandle:
        return attach_payload(handle, payload)

    def get_track_kwargs_from_trace_context(
        self, handle: TraceHandle, **kwargs: Any
    ) -> dict[str, Any]:
        return get_track_kwargs_from_trace_context(handle, **kwargs)


def _build_tracking_context(
    *,
    api_key: str,
    feature: str,
    tenant_id: str,
    customer_id: Optional[str] = None,
    attempt_type: Optional[str] = None,
    plan: Optional[str] = None,
    environment: Optional[str] = None,
    template_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    step_name: Optional[str] = None,
    outcome: Optional[str] = None,
    retry_reason: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    quality_label: Optional[str] = None,
    feedback_score: Optional[float] = None,
    capture_content: bool = False,
    emit_lifecycle_events: bool = False,
    schema_version: Optional[str] = None,
    span_kind: Optional[str] = None,
    tool_name: Optional[str] = None,
    payload_refs: Optional[list[str]] = None,
    payload_blocks: Optional[list[dict[str, Any]]] = None,
    metrics: Optional[dict[str, Any]] = None,
    decision: Optional[dict[str, Any]] = None,
    routing_reason: Optional[str] = None,
    route: Optional[str] = None,
) -> TrackingContext:
    return TrackingContext(
        api_key=api_key,
        feature=feature,
        tenant_id=tenant_id,
        customer_id=customer_id,
        attempt_type=attempt_type,
        plan=plan,
        environment=environment,
        template_id=template_id,
        trace_id=trace_id,
        run_id=run_id,
        conversation_id=conversation_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        step_name=step_name,
        outcome=outcome,
        retry_reason=retry_reason,
        fallback_reason=fallback_reason,
        quality_label=quality_label,
        feedback_score=feedback_score,
        capture_content=capture_content,
        emit_lifecycle_events=emit_lifecycle_events,
        schema_version=schema_version,
        span_kind=span_kind if isinstance(span_kind, str) else None,
        tool_name=tool_name,
        payload_refs=[value for value in (payload_refs or []) if isinstance(value, str) and value.strip()],
        payload_blocks=_normalize_payload_blocks(payload_blocks),
        metrics=_normalize_metrics(metrics),
        decision=_normalize_decision(decision),
        routing_reason=routing_reason,
        route=route,
    )


def track_openai(
    openai_client: Any,
    *,
    api_key: str,
    feature: str,
    tenant_id: str,
    customer_id: Optional[str] = None,
    attempt_type: Optional[str] = None,
    plan: Optional[str] = None,
    environment: Optional[str] = None,
    template_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    step_name: Optional[str] = None,
    outcome: Optional[str] = None,
    retry_reason: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    quality_label: Optional[str] = None,
    feedback_score: Optional[float] = None,
    capture_content: bool = False,
    emit_lifecycle_events: bool = False,
    schema_version: Optional[str] = None,
    span_kind: Optional[str] = None,
    tool_name: Optional[str] = None,
    payload_refs: Optional[list[str]] = None,
    payload_blocks: Optional[list[dict[str, Any]]] = None,
    metrics: Optional[dict[str, Any]] = None,
    decision: Optional[dict[str, Any]] = None,
    routing_reason: Optional[str] = None,
    route: Optional[str] = None,
) -> Any:
    context = TrackingContext(
        api_key=api_key,
        feature=feature,
        tenant_id=tenant_id,
        customer_id=customer_id,
        attempt_type=attempt_type,
        plan=plan,
        environment=environment,
        template_id=template_id,
        trace_id=trace_id,
        run_id=run_id,
        conversation_id=conversation_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        step_name=step_name,
        outcome=outcome,
        retry_reason=retry_reason,
        fallback_reason=fallback_reason,
        quality_label=quality_label,
        feedback_score=feedback_score,
        capture_content=capture_content,
        emit_lifecycle_events=emit_lifecycle_events,
        schema_version=schema_version,
        span_kind=span_kind if isinstance(span_kind, str) else None,
        tool_name=tool_name,
        payload_refs=[value for value in (payload_refs or []) if isinstance(value, str) and value.strip()],
        payload_blocks=_normalize_payload_blocks(payload_blocks),
        metrics=_normalize_metrics(metrics),
        decision=_normalize_decision(decision),
        routing_reason=routing_reason,
        route=route,
    )

    return _TrackedOpenAIClient(openai_client, context)


def track_anthropic(
    anthropic_client: Any,
    *,
    api_key: str,
    feature: str,
    tenant_id: str,
    customer_id: Optional[str] = None,
    attempt_type: Optional[str] = None,
    plan: Optional[str] = None,
    environment: Optional[str] = None,
    template_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    step_name: Optional[str] = None,
    outcome: Optional[str] = None,
    retry_reason: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    quality_label: Optional[str] = None,
    feedback_score: Optional[float] = None,
    capture_content: bool = False,
    emit_lifecycle_events: bool = False,
    schema_version: Optional[str] = None,
    span_kind: Optional[str] = None,
    tool_name: Optional[str] = None,
    payload_refs: Optional[list[str]] = None,
    payload_blocks: Optional[list[dict[str, Any]]] = None,
    metrics: Optional[dict[str, Any]] = None,
    decision: Optional[dict[str, Any]] = None,
    routing_reason: Optional[str] = None,
    route: Optional[str] = None,
) -> Any:
    context = TrackingContext(
        api_key=api_key,
        feature=feature,
        tenant_id=tenant_id,
        customer_id=customer_id,
        attempt_type=attempt_type,
        plan=plan,
        environment=environment,
        template_id=template_id,
        trace_id=trace_id,
        run_id=run_id,
        conversation_id=conversation_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        step_name=step_name,
        outcome=outcome,
        retry_reason=retry_reason,
        fallback_reason=fallback_reason,
        quality_label=quality_label,
        feedback_score=feedback_score,
        capture_content=capture_content,
        emit_lifecycle_events=emit_lifecycle_events,
        schema_version=schema_version,
        span_kind=span_kind if isinstance(span_kind, str) else None,
        tool_name=tool_name,
        payload_refs=[value for value in (payload_refs or []) if isinstance(value, str) and value.strip()],
        payload_blocks=_normalize_payload_blocks(payload_blocks),
        metrics=_normalize_metrics(metrics),
        decision=_normalize_decision(decision),
        routing_reason=routing_reason,
        route=route,
    )

    return _TrackedAnthropicClient(anthropic_client, context)


def track_gemini(
    gemini_client: Any,
    *,
    api_key: str,
    feature: str,
    tenant_id: str,
    customer_id: Optional[str] = None,
    attempt_type: Optional[str] = None,
    plan: Optional[str] = None,
    environment: Optional[str] = None,
    template_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    step_name: Optional[str] = None,
    outcome: Optional[str] = None,
    retry_reason: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    quality_label: Optional[str] = None,
    feedback_score: Optional[float] = None,
    capture_content: bool = False,
    emit_lifecycle_events: bool = False,
    schema_version: Optional[str] = None,
    span_kind: Optional[str] = None,
    tool_name: Optional[str] = None,
    payload_refs: Optional[list[str]] = None,
    payload_blocks: Optional[list[dict[str, Any]]] = None,
    metrics: Optional[dict[str, Any]] = None,
    decision: Optional[dict[str, Any]] = None,
    routing_reason: Optional[str] = None,
    route: Optional[str] = None,
) -> Any:
    context = TrackingContext(
        api_key=api_key,
        feature=feature,
        tenant_id=tenant_id,
        customer_id=customer_id,
        attempt_type=attempt_type,
        plan=plan,
        environment=environment,
        template_id=template_id,
        trace_id=trace_id,
        run_id=run_id,
        conversation_id=conversation_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        step_name=step_name,
        outcome=outcome,
        retry_reason=retry_reason,
        fallback_reason=fallback_reason,
        quality_label=quality_label,
        feedback_score=feedback_score,
        capture_content=capture_content,
        emit_lifecycle_events=emit_lifecycle_events,
        schema_version=schema_version,
        span_kind=span_kind if isinstance(span_kind, str) else None,
        tool_name=tool_name,
        payload_refs=[value for value in (payload_refs or []) if isinstance(value, str) and value.strip()],
        payload_blocks=_normalize_payload_blocks(payload_blocks),
        metrics=_normalize_metrics(metrics),
        decision=_normalize_decision(decision),
        routing_reason=routing_reason,
        route=route,
    )

    return _TrackedGeminiClient(gemini_client, context)


def track_mistral(
    mistral_client: Any,
    *,
    api_key: str,
    feature: str,
    tenant_id: str,
    customer_id: Optional[str] = None,
    attempt_type: Optional[str] = None,
    plan: Optional[str] = None,
    environment: Optional[str] = None,
    template_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    step_name: Optional[str] = None,
    outcome: Optional[str] = None,
    retry_reason: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    quality_label: Optional[str] = None,
    feedback_score: Optional[float] = None,
    capture_content: bool = False,
    emit_lifecycle_events: bool = False,
    schema_version: Optional[str] = None,
    span_kind: Optional[str] = None,
    tool_name: Optional[str] = None,
    payload_refs: Optional[list[str]] = None,
    payload_blocks: Optional[list[dict[str, Any]]] = None,
    metrics: Optional[dict[str, Any]] = None,
    decision: Optional[dict[str, Any]] = None,
    routing_reason: Optional[str] = None,
    route: Optional[str] = None,
) -> Any:
    context = _build_tracking_context(
        api_key=api_key,
        feature=feature,
        tenant_id=tenant_id,
        customer_id=customer_id,
        attempt_type=attempt_type,
        plan=plan,
        environment=environment,
        template_id=template_id,
        trace_id=trace_id,
        run_id=run_id,
        conversation_id=conversation_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        step_name=step_name,
        outcome=outcome,
        retry_reason=retry_reason,
        fallback_reason=fallback_reason,
        quality_label=quality_label,
        feedback_score=feedback_score,
        capture_content=capture_content,
        emit_lifecycle_events=emit_lifecycle_events,
        schema_version=schema_version,
        span_kind=span_kind,
        tool_name=tool_name,
        payload_refs=payload_refs,
        payload_blocks=payload_blocks,
        metrics=metrics,
        decision=decision,
        routing_reason=routing_reason,
        route=route,
    )

    return _TrackedMistralClient(mistral_client, context)


def create_tracer(**kwargs: Any) -> TokveraTracer:
    context = _build_tracking_context(**kwargs)
    return TokveraTracer(context)


class _TrackedOpenAIClient:
    def __init__(self, client: Any, context: TrackingContext) -> None:
        self._client = client
        self._context = context

        self.chat = _ChatNamespace(client.chat, context)
        self.responses = _ResponsesNamespace(client.responses, context)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._client, item)


class _TrackedAnthropicClient:
    def __init__(self, client: Any, context: TrackingContext) -> None:
        self._client = client
        self._context = context
        self.messages = _AnthropicMessagesNamespace(client.messages, context)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._client, item)


class _TrackedGeminiClient:
    def __init__(self, client: Any, context: TrackingContext) -> None:
        self._client = client
        self._context = context
        self.models = _GeminiModelsNamespace(client.models, context)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._client, item)


class _TrackedMistralClient:
    def __init__(self, client: Any, context: TrackingContext) -> None:
        self._client = client
        self._context = context
        self.chat = _MistralChatNamespace(client.chat, context)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._client, item)


class _ChatNamespace:
    def __init__(self, chat: Any, context: TrackingContext) -> None:
        self._chat = chat
        self.completions = _CompletionsNamespace(chat.completions, context)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._chat, item)


class _CompletionsNamespace:
    def __init__(self, completions: Any, context: TrackingContext) -> None:
        self._completions = completions
        self._context = context

    def create(self, *args: Any, **kwargs: Any) -> Any:
        return _tracked_call(
            call=lambda: self._completions.create(*args, **kwargs),
            provider="openai",
            event_type="openai.request",
            endpoint="chat.completions.create",
            context=self._context,
            kwargs=kwargs,
            usage_extractor=_extract_openai_usage,
            model_from_response_extractor=_extract_model_from_response,
        )

    def __getattr__(self, item: str) -> Any:
        return getattr(self._completions, item)


class _ResponsesNamespace:
    def __init__(self, responses: Any, context: TrackingContext) -> None:
        self._responses = responses
        self._context = context

    def create(self, *args: Any, **kwargs: Any) -> Any:
        return _tracked_call(
            call=lambda: self._responses.create(*args, **kwargs),
            provider="openai",
            event_type="openai.request",
            endpoint="responses.create",
            context=self._context,
            kwargs=kwargs,
            usage_extractor=_extract_openai_usage,
            model_from_response_extractor=_extract_model_from_response,
        )

    def __getattr__(self, item: str) -> Any:
        return getattr(self._responses, item)


class _AnthropicMessagesNamespace:
    def __init__(self, messages: Any, context: TrackingContext) -> None:
        self._messages = messages
        self._context = context

    def create(self, *args: Any, **kwargs: Any) -> Any:
        return _tracked_call(
            call=lambda: self._messages.create(*args, **kwargs),
            provider="anthropic",
            event_type="anthropic.request",
            endpoint="messages.create",
            context=self._context,
            kwargs=kwargs,
            usage_extractor=_extract_anthropic_usage,
            model_from_response_extractor=_extract_model_from_response,
        )

    def __getattr__(self, item: str) -> Any:
        return getattr(self._messages, item)


class _GeminiModelsNamespace:
    def __init__(self, models: Any, context: TrackingContext) -> None:
        self._models = models
        self._context = context

        if not hasattr(models, "generate_content") and not hasattr(models, "generateContent"):
            raise AttributeError("Gemini client models namespace must expose generate_content or generateContent.")

    def generate_content(self, *args: Any, **kwargs: Any) -> Any:
        return _tracked_call(
            call=lambda: self._models.generate_content(*args, **kwargs),
            provider="gemini",
            event_type="gemini.request",
            endpoint="models.generate_content",
            context=self._context,
            kwargs=kwargs,
            usage_extractor=_extract_gemini_usage,
            model_from_response_extractor=_extract_gemini_model_from_response,
        )

    def generateContent(self, *args: Any, **kwargs: Any) -> Any:  # noqa: N802
        return _tracked_call(
            call=lambda: self._models.generateContent(*args, **kwargs),
            provider="gemini",
            event_type="gemini.request",
            endpoint="models.generate_content",
            context=self._context,
            kwargs=kwargs,
            usage_extractor=_extract_gemini_usage,
            model_from_response_extractor=_extract_gemini_model_from_response,
        )

    def __getattr__(self, item: str) -> Any:
        return getattr(self._models, item)


class _MistralChatNamespace:
    def __init__(self, chat: Any, context: TrackingContext) -> None:
        self._chat = chat
        self._context = context

    def complete(self, *args: Any, **kwargs: Any) -> Any:
        return _tracked_call(
            call=lambda: self._chat.complete(*args, **kwargs),
            provider="mistral",
            event_type="mistral.request",
            endpoint="chat.complete",
            context=self._context,
            kwargs=kwargs,
            usage_extractor=_extract_openai_usage,
            model_from_response_extractor=_extract_model_from_response,
        )

    def __getattr__(self, item: str) -> Any:
        return getattr(self._chat, item)


def _tracked_call(
    call: Callable[[], Any],
    *,
    provider: str,
    event_type: str,
    endpoint: str,
    context: TrackingContext,
    kwargs: dict[str, Any],
    usage_extractor: Callable[[Any], UsageMetrics],
    model_from_response_extractor: Callable[[Any], Optional[str]],
) -> Any:
    started = time.perf_counter()
    model = _extract_model(kwargs)
    operation_context = (
        context
        if context.trace_id and context.run_id and context.span_id
        else replace(
            context,
            trace_id=context.trace_id or _new_id("trc"),
            run_id=context.run_id or _new_id("run"),
            span_id=context.span_id or _new_id("spn"),
        )
    )
    if operation_context.emit_lifecycle_events:
        lifecycle_event = _build_event(
            provider=provider,
            event_type=event_type,
            endpoint=endpoint,
            context=_strip_terminal_context_fields(operation_context),
            model=model,
            usage=UsageMetrics(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            latency_ms=0,
            status="in_progress",
            kwargs=kwargs,
            response=None,
            error=None,
        )
        _safe_emit(lifecycle_event.to_payload(), api_key=context.api_key)

    try:
        response = call()
    except Exception as exc:
        latency_ms = _elapsed_ms(started)
        event = _build_event(
            provider=provider,
            event_type=event_type,
            endpoint=endpoint,
            context=operation_context,
            model=model,
            usage=UsageMetrics(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            latency_ms=latency_ms,
            status="failure",
            kwargs=kwargs,
            response=None,
            error=exc,
        )
        _safe_emit(event.to_payload(), api_key=context.api_key)
        raise

    latency_ms = _elapsed_ms(started)
    usage = usage_extractor(response)

    event = _build_event(
        provider=provider,
        event_type=event_type,
        endpoint=endpoint,
        context=operation_context,
        model=model or model_from_response_extractor(response),
        usage=usage,
        latency_ms=latency_ms,
        status="success",
        kwargs=kwargs,
        response=response,
        error=None,
    )
    _safe_emit(event.to_payload(), api_key=context.api_key)
    return response


def _build_event(
    *,
    provider: str,
    event_type: str,
    endpoint: str,
    context: TrackingContext,
    model: Optional[str],
    usage: UsageMetrics,
    latency_ms: int,
    status: str,
    kwargs: dict[str, Any],
    response: Any,
    error: Optional[Exception],
) -> AnalyticsEvent:
    prompt_content = _extract_prompt_like(kwargs)
    response_content = _extract_response_content(response)
    prompt_hash: Optional[str] = None
    response_hash: Optional[str] = None
    if context.capture_content:
        prompt_hash = _hash_content(prompt_content)
        response_hash = _hash_content(response_content)

    event_error = None
    if error is not None:
        event_error = EventError(type=error.__class__.__name__, message=str(error))

    trace_id = context.trace_id or _new_id("trc")
    run_id = context.run_id or _new_id("run")
    span_id = context.span_id or _new_id("spn")
    explicit_schema = _normalize_schema_version(context.schema_version)
    span_kind = _normalize_span_kind(context.span_kind)
    tool_name = _normalize_non_empty_string(context.tool_name)
    payload_refs = _normalize_payload_refs(context.payload_refs)
    payload_blocks = _normalize_payload_blocks(context.payload_blocks)
    if context.capture_content:
        payload_blocks = _append_content_payload_blocks(payload_blocks, prompt_content, response_content)
    decision = _build_trace_decision(context)
    metrics = context.metrics or _normalize_metrics({})
    if metrics is None:
        metrics = TraceMetrics()
    metrics = TraceMetrics(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        latency_ms=latency_ms,
        cost_usd=metrics.cost_usd,
    )

    should_use_v2 = (
        explicit_schema == TRACE_SCHEMA_VERSION_V2
        or span_kind is not None
        or tool_name is not None
        or bool(payload_refs)
        or bool(payload_blocks)
        or decision is not None
        or context.metrics is not None
    )
    schema_version = TRACE_SCHEMA_VERSION_V2 if should_use_v2 else TRACE_SCHEMA_VERSION_V1

    return AnalyticsEvent(
        schema_version=schema_version,
        event_type=event_type,
        provider=provider,
        endpoint=endpoint,
        status=status,
        timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        latency_ms=latency_ms,
        model=model or "unknown",
        usage=usage,
        feature=context.feature,
        tenant_id=context.tenant_id,
        customer_id=context.customer_id,
        attempt_type=context.attempt_type,
        plan=context.plan,
        environment=context.environment,
        template_id=context.template_id,
        trace_id=trace_id,
        run_id=run_id,
        conversation_id=context.conversation_id,
        span_id=span_id,
        parent_span_id=context.parent_span_id,
        step_name=context.step_name,
        outcome=context.outcome,
        retry_reason=context.retry_reason,
        fallback_reason=context.fallback_reason,
        quality_label=context.quality_label,
        feedback_score=context.feedback_score,
        prompt_hash=prompt_hash,
        response_hash=response_hash,
        span_kind=span_kind if schema_version == TRACE_SCHEMA_VERSION_V2 else None,
        tool_name=tool_name if schema_version == TRACE_SCHEMA_VERSION_V2 else None,
        payload_refs=payload_refs if schema_version == TRACE_SCHEMA_VERSION_V2 else None,
        payload_blocks=payload_blocks if schema_version == TRACE_SCHEMA_VERSION_V2 else None,
        metrics=metrics if schema_version == TRACE_SCHEMA_VERSION_V2 else None,
        decision=decision if schema_version == TRACE_SCHEMA_VERSION_V2 else None,
        error=event_error,
    )


def _strip_terminal_context_fields(context: TrackingContext) -> TrackingContext:
    return TrackingContext(
        api_key=context.api_key,
        feature=context.feature,
        tenant_id=context.tenant_id,
        customer_id=context.customer_id,
        attempt_type=context.attempt_type,
        plan=context.plan,
        environment=context.environment,
        template_id=context.template_id,
        trace_id=context.trace_id,
        run_id=context.run_id,
        conversation_id=context.conversation_id,
        span_id=context.span_id,
        parent_span_id=context.parent_span_id,
        step_name=context.step_name,
        outcome=None,
        retry_reason=None,
        fallback_reason=None,
        quality_label=None,
        feedback_score=None,
        capture_content=context.capture_content,
        emit_lifecycle_events=context.emit_lifecycle_events,
        schema_version=context.schema_version,
        span_kind=context.span_kind,
        tool_name=context.tool_name,
        payload_refs=context.payload_refs,
        payload_blocks=context.payload_blocks,
        metrics=context.metrics,
        decision=context.decision,
        routing_reason=context.routing_reason,
        route=context.route,
    )


def _extract_model(kwargs: dict[str, Any]) -> Optional[str]:
    model = kwargs.get("model")
    if isinstance(model, str) and model:
        return model
    return None


def _extract_model_from_response(response: Any) -> Optional[str]:
    model = getattr(response, "model", None)
    if isinstance(model, str) and model:
        return model
    return None


def _extract_gemini_model_from_response(response: Any) -> Optional[str]:
    model = getattr(response, "model", None)
    if isinstance(model, str) and model:
        return model

    model_version = getattr(response, "model_version", getattr(response, "modelVersion", None))
    if isinstance(model_version, str) and model_version:
        return model_version
    return None


def _extract_openai_usage(response: Any) -> UsageMetrics:
    usage = getattr(response, "usage", None)
    if usage is None:
        return UsageMetrics(prompt_tokens=0, completion_tokens=0, total_tokens=0)

    prompt_tokens = _to_int(getattr(usage, "prompt_tokens", 0))
    completion_tokens = _to_int(getattr(usage, "completion_tokens", 0))
    total_tokens = _to_int(getattr(usage, "total_tokens", 0))

    return UsageMetrics(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _extract_anthropic_usage(response: Any) -> UsageMetrics:
    usage = getattr(response, "usage", None)
    if usage is None:
        return UsageMetrics(prompt_tokens=0, completion_tokens=0, total_tokens=0)

    prompt_tokens = _to_int(getattr(usage, "input_tokens", getattr(usage, "prompt_tokens", 0)))
    completion_tokens = _to_int(getattr(usage, "output_tokens", getattr(usage, "completion_tokens", 0)))
    total_tokens = _to_int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens))

    return UsageMetrics(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _extract_gemini_usage(response: Any) -> UsageMetrics:
    usage = getattr(response, "usage_metadata", None) or getattr(response, "usageMetadata", None)
    if usage is None:
        return UsageMetrics(prompt_tokens=0, completion_tokens=0, total_tokens=0)

    prompt_tokens = _to_int(
        getattr(usage, "prompt_token_count", getattr(usage, "promptTokenCount", 0))
    )
    completion_tokens = _to_int(
        getattr(
            usage,
            "candidates_token_count",
            getattr(usage, "candidatesTokenCount", getattr(usage, "completion_token_count", 0)),
        )
    )
    total_tokens = _to_int(
        getattr(usage, "total_token_count", getattr(usage, "totalTokenCount", prompt_tokens + completion_tokens))
    )

    return UsageMetrics(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _to_int(value: Any) -> int:
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else 0
    except (TypeError, ValueError):
        return 0


def _extract_prompt_like(kwargs: dict[str, Any]) -> str:
    if "messages" in kwargs:
        return _safe_json(kwargs.get("messages"))
    if "input" in kwargs:
        return _safe_json(kwargs.get("input"))
    if "contents" in kwargs:
        return _safe_json(kwargs.get("contents"))
    if "prompt" in kwargs:
        return _safe_json(kwargs.get("prompt"))
    return ""


def _extract_response_content(response: Any) -> str:
    if response is None:
        return ""

    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text

    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text

    choices = getattr(response, "choices", None)
    if isinstance(choices, Sequence):
        parts: list[str] = []
        for choice in choices:
            message = getattr(choice, "message", None)
            content = getattr(message, "content", None)
            if isinstance(content, str):
                parts.append(content)
        if parts:
            return "\n".join(parts)

    return ""


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def _normalize_non_empty_string(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def _normalize_schema_version(value: Any) -> Optional[str]:
    if value in (TRACE_SCHEMA_VERSION_V1, TRACE_SCHEMA_VERSION_V2):
        return value
    return None


def _normalize_span_kind(value: Any) -> Optional[str]:
    normalized = _normalize_non_empty_string(value)
    if normalized is None:
        return None
    return normalized if normalized in ALLOWED_SPAN_KINDS else None


def _normalize_payload_refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    refs: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if not normalized:
            continue
        refs.append(normalized)
    return refs


def _normalize_payload_type(value: Any) -> str:
    normalized = _normalize_non_empty_string(value)
    if normalized == "prompt":
        return "prompt_input"
    if normalized in ALLOWED_PAYLOAD_TYPES:
        return normalized
    return "other"


def _normalize_payload_blocks(value: Any) -> list[TracePayloadBlock]:
    if not isinstance(value, list):
        return []
    blocks: list[TracePayloadBlock] = []
    for item in value:
        if isinstance(item, TracePayloadBlock):
            payload_type = _normalize_payload_type(item.payload_type)
            content = _normalize_non_empty_string(item.content)
        elif isinstance(item, dict):
            payload_type = _normalize_payload_type(item.get("payload_type") or item.get("payloadType"))
            content = _normalize_non_empty_string(item.get("content"))
        else:
            continue
        if not content:
            continue
        blocks.append(TracePayloadBlock(payload_type=payload_type, content=content))
    return blocks


def _append_content_payload_blocks(
    payload_blocks: list[TracePayloadBlock],
    prompt_content: str,
    response_content: str,
) -> list[TracePayloadBlock]:
    blocks = list(payload_blocks)
    if prompt_content:
        blocks.append(TracePayloadBlock(payload_type="prompt_input", content=prompt_content))
    if response_content:
        blocks.append(TracePayloadBlock(payload_type="model_output", content=response_content))
    return blocks


def _normalize_metrics(value: Any) -> Optional[TraceMetrics]:
    if isinstance(value, TraceMetrics):
        return value
    if not isinstance(value, dict):
        return None
    prompt_tokens = _to_positive_number(value.get("prompt_tokens"))
    completion_tokens = _to_positive_number(value.get("completion_tokens"))
    total_tokens = _to_positive_number(value.get("total_tokens"))
    latency_ms = _to_positive_number(value.get("latency_ms"))
    cost_usd = _to_positive_number(value.get("cost_usd"))
    if cost_usd is None:
        cost_usd = _to_positive_number(value.get("estimated_cost_usd"))
    if (
        prompt_tokens is None
        and completion_tokens is None
        and total_tokens is None
        and latency_ms is None
        and cost_usd is None
    ):
        return None
    return TraceMetrics(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
    )


def _normalize_decision(value: Any) -> Optional[TraceDecision]:
    if isinstance(value, TraceDecision):
        decision = value
    elif isinstance(value, dict):
        decision = TraceDecision(
            outcome=_normalize_non_empty_string(value.get("outcome")),
            retry_reason=_normalize_non_empty_string(value.get("retry_reason")),
            fallback_reason=_normalize_non_empty_string(value.get("fallback_reason")),
            routing_reason=_normalize_non_empty_string(value.get("routing_reason")),
            route=_normalize_non_empty_string(value.get("route")),
        )
    else:
        return None
    if (
        decision.outcome is None
        and decision.retry_reason is None
        and decision.fallback_reason is None
        and decision.routing_reason is None
        and decision.route is None
    ):
        return None
    return decision


def _build_trace_decision(context: TrackingContext) -> Optional[TraceDecision]:
    explicit = _normalize_decision(context.decision)
    if explicit is not None:
        return explicit

    routing_reason = _normalize_non_empty_string(context.routing_reason)
    route = _normalize_non_empty_string(context.route)
    if not routing_reason and not route:
        return None
    return TraceDecision(routing_reason=routing_reason, route=route)


def _to_positive_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _hash_content(content: str) -> Optional[str]:
    if not content:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _safe_emit(payload: dict[str, Any], *, api_key: str) -> None:
    try:
        ingest_event_async(payload, api_key=api_key)
    except Exception:
        # Never fail caller flow because of analytics ingestion.
        return


def _build_context_from_handle(
    handle: TraceHandle,
    overrides: dict[str, Any],
) -> TrackingContext:
    inherited = get_track_kwargs_from_trace_context(handle)
    merged = {**inherited, **overrides}
    merged["trace_id"] = handle.trace_id
    merged["run_id"] = handle.run_id
    merged["span_id"] = handle.span_id
    merged["parent_span_id"] = handle.parent_span_id
    return _build_tracking_context(
        api_key=merged["api_key"],
        feature=merged["feature"],
        tenant_id=merged["tenant_id"],
        customer_id=merged.get("customer_id"),
        attempt_type=merged.get("attempt_type"),
        plan=merged.get("plan"),
        environment=merged.get("environment"),
        template_id=merged.get("template_id"),
        trace_id=handle.trace_id,
        run_id=handle.run_id,
        conversation_id=merged.get("conversation_id"),
        span_id=handle.span_id,
        parent_span_id=handle.parent_span_id,
        step_name=merged.get("step_name"),
        outcome=merged.get("outcome"),
        retry_reason=merged.get("retry_reason"),
        fallback_reason=merged.get("fallback_reason"),
        quality_label=merged.get("quality_label"),
        feedback_score=merged.get("feedback_score"),
        capture_content=bool(merged.get("capture_content", False)),
        emit_lifecycle_events=bool(merged.get("emit_lifecycle_events", False)),
        schema_version=merged.get("schema_version"),
        span_kind=merged.get("span_kind"),
        tool_name=merged.get("tool_name"),
        payload_refs=merged.get("payload_refs"),
        payload_blocks=merged.get("payload_blocks"),
        metrics=merged.get("metrics"),
        decision=merged.get("decision"),
        routing_reason=merged.get("routing_reason"),
        route=merged.get("route"),
    )


def _resolve_trace_contract(
    provider: Optional[str],
    event_type: Optional[str],
    endpoint: Optional[str],
    *,
    root: bool = False,
) -> tuple[str, str, str]:
    normalized = _normalize_non_empty_string(provider) or "tokvera"
    if normalized == "openai":
        return ("openai", _normalize_non_empty_string(event_type) or "openai.request", _normalize_non_empty_string(endpoint) or "responses.create")
    if normalized == "anthropic":
        return ("anthropic", _normalize_non_empty_string(event_type) or "anthropic.request", _normalize_non_empty_string(endpoint) or "messages.create")
    if normalized == "gemini":
        return ("gemini", _normalize_non_empty_string(event_type) or "gemini.request", _normalize_non_empty_string(endpoint) or "models.generate_content")
    if normalized == "mistral":
        return ("mistral", _normalize_non_empty_string(event_type) or "mistral.request", _normalize_non_empty_string(endpoint) or "chat.complete")
    return (
        "tokvera",
        _normalize_non_empty_string(event_type) or "tokvera.trace",
        _normalize_non_empty_string(endpoint) or ("manual.trace" if root else "manual.span"),
    )


def _manual_usage_from_overrides(overrides: dict[str, Any], context: TrackingContext) -> UsageMetrics:
    usage = overrides.get("usage") if isinstance(overrides.get("usage"), dict) else {}
    metrics = context.metrics or TraceMetrics()
    prompt_tokens = int(usage.get("prompt_tokens") or metrics.prompt_tokens or 0)
    completion_tokens = int(usage.get("completion_tokens") or metrics.completion_tokens or 0)
    total_tokens = int(usage.get("total_tokens") or metrics.total_tokens or prompt_tokens + completion_tokens)
    return UsageMetrics(
        prompt_tokens=max(prompt_tokens, 0),
        completion_tokens=max(completion_tokens, 0),
        total_tokens=max(total_tokens, 0),
    )


def _emit_manual_handle_event(
    handle: TraceHandle,
    *,
    status: str,
    overrides: Optional[dict[str, Any]] = None,
    error: Optional[Exception] = None,
) -> None:
    payload_overrides = dict(overrides or {})
    context = _build_context_from_handle(handle, payload_overrides)
    provider, event_type, endpoint = _resolve_trace_contract(
        payload_overrides.get("provider") or handle.provider,
        payload_overrides.get("event_type") or handle.event_type,
        payload_overrides.get("endpoint") or handle.endpoint,
    )
    usage = _manual_usage_from_overrides(payload_overrides, context)
    latency_ms = int(payload_overrides.get("latency_ms") or (0 if status == "in_progress" else max((time.perf_counter() - handle.started_at) * 1000, 0)))
    model = _normalize_non_empty_string(payload_overrides.get("model")) or handle.model or "manual"
    prompt_content = (
        _safe_json(payload_overrides["prompt"])
        if "prompt" in payload_overrides
        else _safe_json(payload_overrides["input"])
        if "input" in payload_overrides
        else None
    )
    response_content = _safe_json(payload_overrides["response"]) if "response" in payload_overrides else None
    event = _build_event(
        provider=provider,
        event_type=event_type,
        endpoint=endpoint,
        context=_strip_terminal_context_fields(context) if status == "in_progress" else context,
        model=model,
        usage=usage,
        latency_ms=latency_ms,
        status=status,
        kwargs={"input": prompt_content} if prompt_content else {},
        response=response_content if response_content is not None else None,
        error=error,
    )
    _safe_emit(event.to_payload(), api_key=context.api_key)


def start_trace(tracer: TokveraTracer, **kwargs: Any) -> TraceHandle:
    provider, event_type, endpoint = _resolve_trace_contract(
        kwargs.get("provider"), kwargs.get("event_type"), kwargs.get("endpoint"), root=True
    )
    trace_id = _normalize_non_empty_string(kwargs.get("trace_id")) or tracer.context.trace_id or _new_id("trc")
    run_id = _normalize_non_empty_string(kwargs.get("run_id")) or tracer.context.run_id or _new_id("run")
    span_id = _normalize_non_empty_string(kwargs.get("span_id")) or _new_id("spn")
    base_context = _build_tracking_context(
        api_key=tracer.context.api_key,
        feature=_normalize_non_empty_string(kwargs.get("feature")) or tracer.context.feature,
        tenant_id=_normalize_non_empty_string(kwargs.get("tenant_id")) or tracer.context.tenant_id,
        customer_id=_normalize_non_empty_string(kwargs.get("customer_id")) or tracer.context.customer_id,
        attempt_type=_normalize_non_empty_string(kwargs.get("attempt_type")) or tracer.context.attempt_type,
        plan=_normalize_non_empty_string(kwargs.get("plan")) or tracer.context.plan,
        environment=_normalize_non_empty_string(kwargs.get("environment")) or tracer.context.environment,
        template_id=_normalize_non_empty_string(kwargs.get("template_id")) or tracer.context.template_id,
        trace_id=trace_id,
        run_id=run_id,
        conversation_id=_normalize_non_empty_string(kwargs.get("conversation_id")) or tracer.context.conversation_id,
        span_id=span_id,
        parent_span_id=None,
        step_name=_normalize_non_empty_string(kwargs.get("step_name")) or tracer.context.step_name,
        outcome=_normalize_non_empty_string(kwargs.get("outcome")) or tracer.context.outcome,
        retry_reason=_normalize_non_empty_string(kwargs.get("retry_reason")) or tracer.context.retry_reason,
        fallback_reason=_normalize_non_empty_string(kwargs.get("fallback_reason")) or tracer.context.fallback_reason,
        quality_label=_normalize_non_empty_string(kwargs.get("quality_label")) or tracer.context.quality_label,
        feedback_score=kwargs.get("feedback_score", tracer.context.feedback_score),
        capture_content=bool(kwargs.get("capture_content", tracer.context.capture_content)),
        emit_lifecycle_events=bool(kwargs.get("emit_lifecycle_events", tracer.context.emit_lifecycle_events)),
        schema_version=kwargs.get("schema_version", tracer.context.schema_version),
        span_kind=kwargs.get("span_kind", tracer.context.span_kind or "orchestrator"),
        tool_name=kwargs.get("tool_name", tracer.context.tool_name),
        payload_refs=kwargs.get("payload_refs", tracer.context.payload_refs),
        payload_blocks=kwargs.get("payload_blocks", tracer.context.payload_blocks),
        metrics=kwargs.get("metrics"),
        decision=kwargs.get("decision"),
        routing_reason=kwargs.get("routing_reason"),
        route=kwargs.get("route"),
    )
    handle = TraceHandle(
        trace_id=trace_id,
        run_id=run_id,
        span_id=span_id,
        parent_span_id=None,
        started_at=time.perf_counter(),
        provider=provider,
        event_type=event_type,
        endpoint=endpoint,
        context=base_context,
        model=_normalize_non_empty_string(kwargs.get("model")),
    )
    _emit_manual_handle_event(handle, status="in_progress", overrides=kwargs)
    return handle


def start_span(parent: TraceHandle, **kwargs: Any) -> TraceHandle:
    provider, event_type, endpoint = _resolve_trace_contract(
        kwargs.get("provider"), kwargs.get("event_type"), kwargs.get("endpoint"), root=False
    )
    context_kwargs = get_track_kwargs_from_trace_context(parent, **kwargs)
    base_context = _build_tracking_context(**context_kwargs)
    handle = TraceHandle(
        trace_id=parent.trace_id,
        run_id=parent.run_id,
        span_id=base_context.span_id or _new_id("spn"),
        parent_span_id=base_context.parent_span_id,
        started_at=time.perf_counter(),
        provider=provider,
        event_type=event_type,
        endpoint=endpoint,
        context=base_context,
        model=_normalize_non_empty_string(kwargs.get("model")),
    )
    _emit_manual_handle_event(handle, status="in_progress", overrides=kwargs)
    return handle


def finish_span(handle: TraceHandle, **kwargs: Any) -> None:
    _emit_manual_handle_event(handle, status="success", overrides=kwargs)


def fail_span(handle: TraceHandle, error: Any, **kwargs: Any) -> None:
    normalized = error if isinstance(error, Exception) else RuntimeError(str(error))
    _emit_manual_handle_event(handle, status="failure", overrides=kwargs, error=normalized)


def attach_payload(handle: TraceHandle, payload: Any) -> TraceHandle:
    current = list(handle.context.payload_blocks or [])
    if isinstance(payload, dict):
        current.extend(_normalize_payload_blocks([payload]))
    elif isinstance(payload, TracePayloadBlock):
        current.extend(_normalize_payload_blocks([payload]))
    elif isinstance(payload, list):
        current.extend(_normalize_payload_blocks(payload))
    handle.context = replace(handle.context, payload_blocks=current)
    return handle


def get_track_kwargs_from_trace_context(handle: TraceHandle, **kwargs: Any) -> dict[str, Any]:
    return {
        "api_key": handle.context.api_key,
        "feature": kwargs.get("feature", handle.context.feature),
        "tenant_id": kwargs.get("tenant_id", handle.context.tenant_id),
        "customer_id": kwargs.get("customer_id", handle.context.customer_id),
        "attempt_type": kwargs.get("attempt_type", handle.context.attempt_type),
        "plan": kwargs.get("plan", handle.context.plan),
        "environment": kwargs.get("environment", handle.context.environment),
        "template_id": kwargs.get("template_id", handle.context.template_id),
        "trace_id": kwargs.get("trace_id", handle.trace_id),
        "run_id": kwargs.get("run_id", handle.run_id),
        "conversation_id": kwargs.get("conversation_id", handle.context.conversation_id),
        "span_id": kwargs.get("span_id", _new_id("spn")),
        "parent_span_id": kwargs.get("parent_span_id", handle.span_id),
        "step_name": kwargs.get("step_name", handle.context.step_name),
        "outcome": kwargs.get("outcome", handle.context.outcome),
        "retry_reason": kwargs.get("retry_reason", handle.context.retry_reason),
        "fallback_reason": kwargs.get("fallback_reason", handle.context.fallback_reason),
        "quality_label": kwargs.get("quality_label", handle.context.quality_label),
        "feedback_score": kwargs.get("feedback_score", handle.context.feedback_score),
        "capture_content": kwargs.get("capture_content", handle.context.capture_content),
        "emit_lifecycle_events": kwargs.get(
            "emit_lifecycle_events", handle.context.emit_lifecycle_events
        ),
        "schema_version": kwargs.get("schema_version", handle.context.schema_version),
        "span_kind": kwargs.get("span_kind", handle.context.span_kind),
        "tool_name": kwargs.get("tool_name", handle.context.tool_name),
        "payload_refs": kwargs.get("payload_refs", handle.context.payload_refs),
        "payload_blocks": kwargs.get("payload_blocks", handle.context.payload_blocks),
        "metrics": kwargs.get("metrics", handle.context.metrics),
        "decision": kwargs.get("decision", handle.context.decision),
        "routing_reason": kwargs.get("routing_reason", handle.context.routing_reason),
        "route": kwargs.get("route", handle.context.route),
    }


class TokveraOTelSpanExporter:
    def __init__(self, **kwargs: Any) -> None:
        self.context = _build_tracking_context(**kwargs)

    def export(self, spans: list[Any]) -> None:
        for span in spans:
            attributes = getattr(span, "attributes", {}) or {}
            resource = getattr(getattr(span, "resource", None), "attributes", {}) or {}
            context_factory = getattr(span, "get_span_context", None) or getattr(span, "span_context", None)
            if callable(context_factory):
                span_context = context_factory()
            else:
                span_context = None
            trace_id = _normalize_non_empty_string(getattr(span_context, "trace_id", None)) or _new_id("trc")
            span_id = _normalize_non_empty_string(getattr(span_context, "span_id", None)) or _new_id("spn")
            parent_span_id = _normalize_non_empty_string(getattr(span, "parent_span_id", None))
            start_time = float(getattr(span, "start_time", time.time()))
            end_time = float(getattr(span, "end_time", time.time()))
            duration_ms = max(int((end_time - start_time) * 1000), 0)
            provider = _normalize_non_empty_string(attributes.get("tokvera.provider")) or "tokvera"
            provider_contract = _resolve_trace_contract(provider, None, attributes.get("tokvera.endpoint"))
            handle = TraceHandle(
                trace_id=trace_id,
                run_id=_normalize_non_empty_string(attributes.get("tokvera.run_id")) or trace_id.replace("trc_", "run_", 1),
                span_id=span_id,
                parent_span_id=parent_span_id,
                started_at=time.perf_counter(),
                provider=provider_contract[0],
                event_type=provider_contract[1],
                endpoint=provider_contract[2] if provider_contract[0] != "tokvera" else "otel.span",
                context=_build_tracking_context(
                    api_key=self.context.api_key,
                    feature=_normalize_non_empty_string(attributes.get("tokvera.feature")) or _normalize_non_empty_string(resource.get("service.name")) or self.context.feature,
                    tenant_id=_normalize_non_empty_string(attributes.get("tokvera.tenant_id")) or self.context.tenant_id,
                    customer_id=_normalize_non_empty_string(attributes.get("tokvera.customer_id")) or self.context.customer_id,
                    attempt_type=self.context.attempt_type,
                    plan=self.context.plan,
                    environment=_normalize_non_empty_string(resource.get("deployment.environment")) or self.context.environment,
                    template_id=self.context.template_id,
                    trace_id=trace_id,
                    run_id=_normalize_non_empty_string(attributes.get("tokvera.run_id")) or trace_id.replace("trc_", "run_", 1),
                    conversation_id=self.context.conversation_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    step_name=_normalize_non_empty_string(attributes.get("tokvera.step_name")) or _normalize_non_empty_string(getattr(span, "name", None)),
                    capture_content=False,
                    emit_lifecycle_events=False,
                    schema_version=TRACE_SCHEMA_VERSION_V2,
                    span_kind=_normalize_non_empty_string(attributes.get("tokvera.span_kind")) or ("model" if provider != "tokvera" else "orchestrator"),
                    tool_name=_normalize_non_empty_string(attributes.get("tokvera.tool_name")),
                    metrics={
                        "prompt_tokens": attributes.get("gen_ai.usage.input_tokens") or attributes.get("tokvera.prompt_tokens"),
                        "completion_tokens": attributes.get("gen_ai.usage.output_tokens") or attributes.get("tokvera.completion_tokens"),
                        "total_tokens": attributes.get("tokvera.total_tokens"),
                        "latency_ms": duration_ms,
                        "cost_usd": attributes.get("tokvera.cost_usd"),
                    },
                    payload_blocks=[
                        {
                            "payload_type": "context",
                            "content": _safe_json(
                                {
                                    "name": getattr(span, "name", None),
                                    "attributes": attributes,
                                }
                            ),
                        }
                    ],
                ),
                model=_normalize_non_empty_string(attributes.get("gen_ai.response.model")) or _normalize_non_empty_string(attributes.get("llm.model_name")),
            )
            _emit_manual_handle_event(
                handle,
                status="failure" if getattr(getattr(span, "status", None), "is_ok", True) is False else "success",
                overrides={
                    "provider": handle.provider,
                    "event_type": handle.event_type,
                    "endpoint": handle.endpoint,
                    "model": handle.model,
                    "latency_ms": duration_ms,
                    "usage": {
                        "prompt_tokens": attributes.get("gen_ai.usage.input_tokens") or 0,
                        "completion_tokens": attributes.get("gen_ai.usage.output_tokens") or 0,
                        "total_tokens": attributes.get("tokvera.total_tokens") or 0,
                    },
                },
                error=RuntimeError(str(getattr(getattr(span, "status", None), "description", "OTel span failed")))
                if getattr(getattr(span, "status", None), "is_ok", True) is False
                else None,
            )


# TODO: Add async wrapper support in a future version.
