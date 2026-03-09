from __future__ import annotations

import datetime as dt
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from ..ingest import ingest_event_async

try:
    from llama_index.core.callbacks.base_handler import BaseCallbackHandler
except Exception:  # pragma: no cover - optional dependency
    class BaseCallbackHandler:  # type: ignore[no-redef]
        pass


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _to_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    text = str(value).strip()
    return text or None


def _to_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_mapping_value(source: Any, key: str) -> Any:
    if not isinstance(source, Mapping):
        return None
    return source.get(key)


def _read_string(source: Any, key: str) -> Optional[str]:
    return _to_string(_read_mapping_value(source, key))


def _read_number(source: Any, key: str) -> Optional[float]:
    return _to_number(_read_mapping_value(source, key))


def _sanitize_component(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", str(value or ""))[:48]


def _derived_id(prefix: str, source: Any) -> str:
    component = _sanitize_component(source)
    if not component:
        return _new_id(prefix)
    return f"{prefix}_{component.lower()}"


def _infer_provider(model: Optional[str]) -> str:
    normalized = (model or "").lower()
    if "claude" in normalized:
        return "anthropic"
    if "gemini" in normalized:
        return "gemini"
    return "openai"


def _contract(provider: str, endpoint: Optional[str]) -> tuple[str, str, str]:
    if provider == "anthropic":
        return ("anthropic", "anthropic.request", endpoint or "messages.create")
    if provider == "gemini":
        return ("gemini", "gemini.request", endpoint or "models.generate_content")
    return ("openai", "openai.request", endpoint or "chat.completions.create")


def _normalize_payload_type(value: Any) -> str:
    normalized = _to_string(value)
    if normalized == "prompt":
        return "prompt_input"
    if normalized in ALLOWED_PAYLOAD_TYPES:
        return normalized
    return "other"


def _apply_trace_v2_fields(payload: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    schema_version = _to_string(options.get("schema_version"))
    span_kind = _to_string(options.get("span_kind"))
    if span_kind not in ALLOWED_SPAN_KINDS:
        span_kind = None
    tool_name = _to_string(options.get("tool_name"))

    payload_refs_raw = options.get("payload_refs")
    payload_refs = (
        [item.strip() for item in payload_refs_raw if isinstance(item, str) and item.strip()]
        if isinstance(payload_refs_raw, list)
        else []
    )

    payload_blocks_raw = options.get("payload_blocks")
    payload_blocks: list[dict[str, Any]] = []
    if isinstance(payload_blocks_raw, list):
        for item in payload_blocks_raw:
            if not isinstance(item, Mapping):
                continue
            content = _to_string(item.get("content"))
            if not content:
                continue
            payload_blocks.append(
                {
                    "payload_type": _normalize_payload_type(item.get("payload_type") or item.get("payloadType")),
                    "content": content,
                }
            )

    metrics = options.get("metrics") if isinstance(options.get("metrics"), Mapping) else {}
    normalized_metrics = {
        "prompt_tokens": metrics.get("prompt_tokens"),
        "completion_tokens": metrics.get("completion_tokens"),
        "total_tokens": metrics.get("total_tokens"),
        "latency_ms": metrics.get("latency_ms"),
        "cost_usd": metrics.get("cost_usd", metrics.get("estimated_cost_usd")),
    }
    normalized_metrics = {key: value for key, value in normalized_metrics.items() if value is not None}

    decision = options.get("decision") if isinstance(options.get("decision"), Mapping) else {}
    normalized_decision = {
        "outcome": _to_string(decision.get("outcome")),
        "retry_reason": _to_string(decision.get("retry_reason")),
        "fallback_reason": _to_string(decision.get("fallback_reason")),
        "routing_reason": _to_string(decision.get("routing_reason") or options.get("routing_reason")),
        "route": _to_string(decision.get("route") or options.get("route")),
    }
    normalized_decision = {key: value for key, value in normalized_decision.items() if value is not None}

    should_use_v2 = (
        schema_version == TRACE_SCHEMA_VERSION_V2
        or span_kind is not None
        or tool_name is not None
        or len(payload_refs) > 0
        or len(payload_blocks) > 0
        or len(normalized_metrics) > 0
        or len(normalized_decision) > 0
    )
    if not should_use_v2:
        return payload

    payload["schema_version"] = TRACE_SCHEMA_VERSION_V2
    if span_kind is not None:
        payload["span_kind"] = span_kind
    if tool_name is not None:
        payload["tool_name"] = tool_name
    if payload_refs:
        payload["payload_refs"] = payload_refs
    if payload_blocks:
        payload["payload_blocks"] = payload_blocks
    if normalized_metrics:
        payload["metrics"] = normalized_metrics
    if normalized_decision:
        payload["decision"] = normalized_decision
    return payload


def _extract_usage(payload: Any) -> dict[str, int]:
    usage = _read_mapping_value(payload, "usage")
    if not isinstance(usage, Mapping):
        usage = {}
    token_usage = _read_mapping_value(payload, "token_usage")
    if not isinstance(token_usage, Mapping):
        token_usage = {}

    prompt_tokens = (
        _read_number(payload, "prompt_tokens")
        or _read_number(usage, "prompt_tokens")
        or _read_number(token_usage, "prompt_tokens")
        or _read_number(token_usage, "promptTokens")
        or _read_number(payload, "input_tokens")
        or 0
    )
    completion_tokens = (
        _read_number(payload, "completion_tokens")
        or _read_number(usage, "completion_tokens")
        or _read_number(token_usage, "completion_tokens")
        or _read_number(token_usage, "completionTokens")
        or _read_number(payload, "output_tokens")
        or 0
    )
    total_tokens = (
        _read_number(payload, "total_tokens")
        or _read_number(usage, "total_tokens")
        or _read_number(token_usage, "total_tokens")
        or _read_number(token_usage, "totalTokens")
        or prompt_tokens + completion_tokens
    )

    return {
        "prompt_tokens": max(0, int(prompt_tokens)),
        "completion_tokens": max(0, int(completion_tokens)),
        "total_tokens": max(0, int(total_tokens)),
    }


@dataclass
class _EventSnapshot:
    started_at: float
    provider: str
    event_type: str
    endpoint: str
    model: str
    tags: dict[str, Any]
    evaluation: Optional[dict[str, Any]]


class TokveraLlamaIndexCallbackHandler(BaseCallbackHandler):
    def __init__(
        self,
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
        provider: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        schema_version: Optional[str] = None,
        span_kind: Optional[str] = None,
        tool_name: Optional[str] = None,
        payload_refs: Optional[list[str]] = None,
        payload_blocks: Optional[list[dict[str, Any]]] = None,
        metrics: Optional[dict[str, Any]] = None,
        decision: Optional[dict[str, Any]] = None,
        routing_reason: Optional[str] = None,
        route: Optional[str] = None,
    ) -> None:
        self._options = {
            "api_key": api_key,
            "feature": feature,
            "tenant_id": tenant_id,
            "customer_id": customer_id,
            "attempt_type": attempt_type,
            "plan": plan,
            "environment": environment,
            "template_id": template_id,
            "trace_id": trace_id,
            "run_id": run_id,
            "conversation_id": conversation_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "step_name": step_name,
            "outcome": outcome,
            "retry_reason": retry_reason,
            "fallback_reason": fallback_reason,
            "quality_label": quality_label,
            "feedback_score": feedback_score,
            "provider": provider,
            "endpoint": endpoint,
            "model": model,
            "schema_version": schema_version,
            "span_kind": span_kind,
            "tool_name": tool_name,
            "payload_refs": payload_refs,
            "payload_blocks": payload_blocks,
            "metrics": metrics,
            "decision": decision,
            "routing_reason": routing_reason,
            "route": route,
        }
        self._events: dict[str, _EventSnapshot] = {}

    # LlamaIndex callback API
    def start_trace(self, trace_id: Optional[str] = None) -> None:  # pragma: no cover - interface hook
        return None

    # LlamaIndex callback API
    def end_trace(
        self,
        trace_id: Optional[str] = None,
        trace_map: Optional[dict[str, list[str]]] = None,
    ) -> None:  # pragma: no cover - interface hook
        return None

    # LlamaIndex callback API
    @property
    def event_starts_to_ignore(self) -> list[Any]:  # pragma: no cover - interface hook
        return []

    # LlamaIndex callback API
    @property
    def event_ends_to_ignore(self) -> list[Any]:  # pragma: no cover - interface hook
        return []

    # LlamaIndex callback API
    def on_event_start(
        self,
        event_type: Any,
        payload: Optional[dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        normalized_payload = payload or {}
        event_key = event_id or _new_id("evt")
        parent_key = parent_id or None
        parent_snapshot = self._events.get(parent_key) if parent_key else None
        event_type_name = _to_string(event_type) or "llm"

        model = (
            _to_string(self._options.get("model"))
            or _read_string(normalized_payload, "model")
            or _read_string(normalized_payload, "model_name")
            or _read_string(normalized_payload, "modelName")
            or "unknown"
        )
        provider = _to_string(self._options.get("provider")) or _infer_provider(model)
        provider, event_name, endpoint = _contract(provider, _to_string(self._options.get("endpoint")))

        trace_id = (
            _to_string(self._options.get("trace_id"))
            or _read_string(normalized_payload, "trace_id")
            or (parent_snapshot.tags.get("trace_id") if parent_snapshot else None)
            or _derived_id("trc", parent_key or event_key)
        )
        run_id = (
            _to_string(self._options.get("run_id"))
            or _read_string(normalized_payload, "run_id")
            or (parent_snapshot.tags.get("run_id") if parent_snapshot else None)
            or event_key
        )
        span_id = (
            _to_string(self._options.get("span_id"))
            or _read_string(normalized_payload, "span_id")
            or _derived_id("spn", event_key)
        )
        parent_span_id = (
            _to_string(self._options.get("parent_span_id"))
            or _read_string(normalized_payload, "parent_span_id")
            or (parent_snapshot.tags.get("span_id") if parent_snapshot else None)
            or (_derived_id("spn", parent_key) if parent_key else None)
        )
        tags = {
            "feature": _to_string(self._options.get("feature")),
            "tenant_id": _to_string(self._options.get("tenant_id")),
            "customer_id": _to_string(self._options.get("customer_id")),
            "attempt_type": _to_string(self._options.get("attempt_type")),
            "plan": _to_string(self._options.get("plan")),
            "environment": _to_string(self._options.get("environment")),
            "template_id": _to_string(self._options.get("template_id")),
            "trace_id": trace_id,
            "run_id": run_id,
            "conversation_id": _to_string(self._options.get("conversation_id"))
            or _read_string(normalized_payload, "conversation_id"),
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "step_name": _to_string(self._options.get("step_name")) or event_type_name.lower(),
            "outcome": _to_string(self._options.get("outcome")) or _read_string(normalized_payload, "outcome"),
            "retry_reason": _to_string(self._options.get("retry_reason"))
            or _read_string(normalized_payload, "retry_reason"),
            "fallback_reason": _to_string(self._options.get("fallback_reason"))
            or _read_string(normalized_payload, "fallback_reason"),
            "quality_label": _to_string(self._options.get("quality_label"))
            or _read_string(normalized_payload, "quality_label"),
            "feedback_score": _to_number(self._options.get("feedback_score"))
            if _to_number(self._options.get("feedback_score")) is not None
            else _read_number(normalized_payload, "feedback_score"),
        }
        tags = {key: value for key, value in tags.items() if value is not None}

        evaluation = {
            "outcome": tags.get("outcome"),
            "retry_reason": tags.get("retry_reason"),
            "fallback_reason": tags.get("fallback_reason"),
            "quality_label": tags.get("quality_label"),
            "feedback_score": tags.get("feedback_score"),
        }
        evaluation = {key: value for key, value in evaluation.items() if value is not None}

        self._events[event_key] = _EventSnapshot(
            started_at=time.time(),
            provider=provider,
            event_type=event_name,
            endpoint=endpoint,
            model=model,
            tags=tags,
            evaluation=evaluation or None,
        )
        return event_key

    # LlamaIndex callback API
    def on_event_end(
        self,
        event_type: Any,
        payload: Optional[dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        event_key = event_id or _new_id("evt")
        snapshot = self._events.pop(event_key, None)
        if snapshot is None:
            event_key = self.on_event_start(event_type, payload=payload, event_id=event_key, **kwargs)
            snapshot = self._events.pop(event_key)

        normalized_payload = payload or {}
        latency_ms = max(0, int((time.time() - snapshot.started_at) * 1000))
        usage = _extract_usage(normalized_payload)

        payload_event = {
            "schema_version": TRACE_SCHEMA_VERSION_V1,
            "event_type": snapshot.event_type,
            "provider": snapshot.provider,
            "endpoint": snapshot.endpoint,
            "status": "success",
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "latency_ms": latency_ms,
            "model": snapshot.model,
            "usage": usage,
            "tags": snapshot.tags,
        }
        if snapshot.evaluation:
            payload_event["evaluation"] = snapshot.evaluation

        payload_event = _apply_trace_v2_fields(payload_event, self._options)

        ingest_event_async(payload_event, api_key=str(self._options["api_key"]))

    def on_event_error(
        self,
        event_type: Any,
        error: BaseException,
        payload: Optional[dict[str, Any]] = None,
        event_id: str = "",
    ) -> None:
        event_key = event_id or _new_id("evt")
        snapshot = self._events.pop(event_key, None)
        if snapshot is None:
            event_key = self.on_event_start(event_type, payload=payload, event_id=event_key)
            snapshot = self._events.pop(event_key)

        latency_ms = max(0, int((time.time() - snapshot.started_at) * 1000))
        tags = dict(snapshot.tags)
        tags.setdefault("outcome", "failure")

        payload_event = {
            "schema_version": TRACE_SCHEMA_VERSION_V1,
            "event_type": snapshot.event_type,
            "provider": snapshot.provider,
            "endpoint": snapshot.endpoint,
            "status": "failure",
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "latency_ms": latency_ms,
            "model": snapshot.model,
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "tags": tags,
            "error": {
                "type": error.__class__.__name__,
                "message": str(error),
            },
        }
        if snapshot.evaluation:
            evaluation = dict(snapshot.evaluation)
            evaluation.setdefault("outcome", "failure")
            payload_event["evaluation"] = evaluation

        payload_event = _apply_trace_v2_fields(payload_event, self._options)

        ingest_event_async(payload_event, api_key=str(self._options["api_key"]))


def create_llamaindex_callback_handler(**kwargs: Any) -> TokveraLlamaIndexCallbackHandler:
    return TokveraLlamaIndexCallbackHandler(**kwargs)
TRACE_SCHEMA_VERSION_V1 = "2026-02-16"
TRACE_SCHEMA_VERSION_V2 = "2026-04-01"
ALLOWED_SPAN_KINDS = {"model", "tool", "orchestrator", "retrieval", "guardrail"}
ALLOWED_PAYLOAD_TYPES = {"prompt_input", "tool_input", "tool_output", "model_output", "context", "other"}
