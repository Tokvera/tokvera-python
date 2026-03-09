from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
import uuid
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

    try:
        response = call()
    except Exception as exc:
        latency_ms = _elapsed_ms(started)
        event = _build_event(
            provider=provider,
            event_type=event_type,
            endpoint=endpoint,
            context=context,
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
        context=context,
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
        status="success" if status == "success" else "failure",
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
        run_id=context.run_id,
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


# TODO: Add async wrapper support in a future version.
