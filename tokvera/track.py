from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from typing import Any, Callable, Optional, Sequence

from .ingest import ingest_event_async
from .types import AnalyticsEvent, EventError, TrackingContext, UsageMetrics


def track_openai(
    openai_client: Any,
    *,
    api_key: str,
    feature: str,
    tenant_id: str,
    customer_id: Optional[str] = None,
    plan: Optional[str] = None,
    environment: Optional[str] = None,
    template_id: Optional[str] = None,
    capture_content: bool = False,
) -> Any:
    context = TrackingContext(
        api_key=api_key,
        feature=feature,
        tenant_id=tenant_id,
        customer_id=customer_id,
        plan=plan,
        environment=environment,
        template_id=template_id,
        capture_content=capture_content,
    )

    return _TrackedOpenAIClient(openai_client, context)


class _TrackedOpenAIClient:
    def __init__(self, client: Any, context: TrackingContext) -> None:
        self._client = client
        self._context = context

        self.chat = _ChatNamespace(client.chat, context)
        self.responses = _ResponsesNamespace(client.responses, context)

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
            endpoint="chat.completions.create",
            context=self._context,
            kwargs=kwargs,
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
            endpoint="responses.create",
            context=self._context,
            kwargs=kwargs,
        )

    def __getattr__(self, item: str) -> Any:
        return getattr(self._responses, item)


def _tracked_call(
    call: Callable[[], Any],
    *,
    endpoint: str,
    context: TrackingContext,
    kwargs: dict[str, Any],
) -> Any:
    started = time.perf_counter()
    model = _extract_model(kwargs)

    try:
        response = call()
    except Exception as exc:
        latency_ms = _elapsed_ms(started)
        event = _build_event(
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
    usage = _extract_usage(response)

    event = _build_event(
        endpoint=endpoint,
        context=context,
        model=model or _extract_model_from_response(response),
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
    prompt_hash: Optional[str] = None
    response_hash: Optional[str] = None

    if context.capture_content:
        prompt_hash = _hash_content(_extract_prompt_like(kwargs))
        response_hash = _hash_content(_extract_response_content(response))

    event_error = None
    if error is not None:
        event_error = EventError(type=error.__class__.__name__, message=str(error))

    return AnalyticsEvent(
        schema_version="2026-02-16",
        event_type="openai.request",
        provider="openai",
        endpoint=endpoint,
        status="success" if status == "success" else "failure",
        timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        latency_ms=latency_ms,
        model=model or "unknown",
        usage=usage,
        feature=context.feature,
        tenant_id=context.tenant_id,
        customer_id=context.customer_id,
        plan=context.plan,
        environment=context.environment,
        template_id=context.template_id,
        prompt_hash=prompt_hash,
        response_hash=response_hash,
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


def _extract_usage(response: Any) -> UsageMetrics:
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


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _extract_prompt_like(kwargs: dict[str, Any]) -> str:
    if "messages" in kwargs:
        return _safe_json(kwargs.get("messages"))
    if "input" in kwargs:
        return _safe_json(kwargs.get("input"))
    return ""


def _extract_response_content(response: Any) -> str:
    if response is None:
        return ""

    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text

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


def _hash_content(content: str) -> Optional[str]:
    if not content:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _safe_emit(payload: dict[str, Any], *, api_key: str) -> None:
    try:
        ingest_event_async(payload, api_key=api_key)
    except Exception:
        # Never fail caller flow because of analytics ingestion.
        return


# TODO: Add async OpenAI client wrapper support in a future version.
