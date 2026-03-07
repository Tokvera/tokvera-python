from __future__ import annotations

import datetime as dt
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from ..ingest import ingest_event_async

try:
    from langchain_core.callbacks import BaseCallbackHandler
except Exception:  # pragma: no cover - optional dependency
    class BaseCallbackHandler:  # type: ignore[no-redef]
        pass


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _sanitize_component(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", str(value or ""))[:48]


def _derived_id(prefix: str, source: Any) -> str:
    component = _sanitize_component(source)
    if not component:
        return _new_id(prefix)
    return f"{prefix}_{component.lower()}"


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


def _extract_usage(response: Any) -> dict[str, int]:
    llm_output = getattr(response, "llm_output", None) or getattr(response, "llmOutput", None)
    if not isinstance(llm_output, Mapping):
        llm_output = {}

    token_usage = _read_mapping_value(llm_output, "token_usage") or _read_mapping_value(
        llm_output, "tokenUsage"
    )
    if not isinstance(token_usage, Mapping):
        token_usage = {}

    usage = _read_mapping_value(llm_output, "usage")
    if not isinstance(usage, Mapping):
        usage = {}

    usage_metadata = _read_mapping_value(llm_output, "usage_metadata") or _read_mapping_value(
        llm_output, "usageMetadata"
    )
    if not isinstance(usage_metadata, Mapping):
        usage_metadata = {}

    prompt_tokens = (
        _read_number(token_usage, "prompt_tokens")
        or _read_number(token_usage, "promptTokens")
        or _read_number(token_usage, "input_tokens")
        or _read_number(usage, "prompt_tokens")
        or _read_number(usage, "input_tokens")
        or _read_number(usage_metadata, "prompt_token_count")
        or _read_number(usage_metadata, "promptTokenCount")
        or 0
    )
    completion_tokens = (
        _read_number(token_usage, "completion_tokens")
        or _read_number(token_usage, "completionTokens")
        or _read_number(token_usage, "output_tokens")
        or _read_number(usage, "completion_tokens")
        or _read_number(usage, "output_tokens")
        or _read_number(usage_metadata, "candidates_token_count")
        or _read_number(usage_metadata, "candidatesTokenCount")
        or 0
    )
    total_tokens = (
        _read_number(token_usage, "total_tokens")
        or _read_number(token_usage, "totalTokens")
        or _read_number(usage, "total_tokens")
        or _read_number(usage_metadata, "total_token_count")
        or _read_number(usage_metadata, "totalTokenCount")
        or prompt_tokens + completion_tokens
    )

    return {
        "prompt_tokens": max(0, int(prompt_tokens)),
        "completion_tokens": max(0, int(completion_tokens)),
        "total_tokens": max(0, int(total_tokens)),
    }


@dataclass
class _RunSnapshot:
    started_at: float
    provider: str
    event_type: str
    endpoint: str
    model: Optional[str]
    tags: dict[str, Any]
    evaluation: Optional[dict[str, Any]]


class TokveraLangChainCallbackHandler(BaseCallbackHandler):
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
        run_id_as_trace_id: bool = False,
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
            "run_id_as_trace_id": run_id_as_trace_id,
        }
        self._runs: dict[str, _RunSnapshot] = {}

    @property
    def always_verbose(self) -> bool:  # pragma: no cover - interface flag
        return False

    def on_llm_start(
        self,
        serialized: Any,
        prompts: list[str],
        run_id: Any,
        parent_run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        metadata = kwargs.get("metadata")
        invocation_params = kwargs.get("invocation_params") or kwargs.get("invocationParams")
        name = kwargs.get("name")
        run_key = str(run_id)
        parent_key = str(parent_run_id) if parent_run_id is not None else None
        parent_snapshot = self._runs.get(parent_key) if parent_key else None

        serialized_kwargs = _read_mapping_value(serialized, "kwargs")
        model = (
            _to_string(self._options.get("model"))
            or _read_string(metadata, "model")
            or _read_string(serialized_kwargs, "model")
            or _read_string(serialized_kwargs, "model_name")
            or _read_string(serialized_kwargs, "modelName")
            or _read_string(invocation_params, "model")
            or _read_string(invocation_params, "model_name")
            or _read_string(invocation_params, "modelName")
        )
        provider = _to_string(self._options.get("provider")) or _read_string(metadata, "provider") or _infer_provider(model)
        provider, event_type, endpoint = _contract(provider, _to_string(self._options.get("endpoint")))

        configured_feedback = _to_number(self._options.get("feedback_score"))
        metadata_feedback = _read_number(metadata, "feedback_score")
        feedback_score = configured_feedback if configured_feedback is not None else metadata_feedback

        run_trace = _derived_id("trc", parent_key or run_key) if self._options.get("run_id_as_trace_id") else None
        trace_id = (
            _to_string(self._options.get("trace_id"))
            or _read_string(metadata, "trace_id")
            or (parent_snapshot.tags.get("trace_id") if parent_snapshot else None)
            or run_trace
            or _derived_id("trc", parent_key or run_key)
        )
        run_id_tag = (
            _to_string(self._options.get("run_id"))
            or _read_string(metadata, "run_id")
            or (parent_snapshot.tags.get("run_id") if parent_snapshot else None)
            or _to_string(run_key)
        )
        conversation_id = (
            _to_string(self._options.get("conversation_id"))
            or _read_string(metadata, "conversation_id")
            or (parent_snapshot.tags.get("conversation_id") if parent_snapshot else None)
        )
        span_id = (
            _to_string(self._options.get("span_id"))
            or _read_string(metadata, "span_id")
            or _derived_id("spn", run_key)
        )
        parent_span_id = (
            _to_string(self._options.get("parent_span_id"))
            or _read_string(metadata, "parent_span_id")
            or (parent_snapshot.tags.get("span_id") if parent_snapshot else None)
            or (_derived_id("spn", parent_key) if parent_key else None)
        )
        step_name = (
            _to_string(self._options.get("step_name"))
            or _read_string(metadata, "step_name")
            or _to_string(name)
        )
        tags = {
            "feature": _to_string(self._options.get("feature")) or _read_string(metadata, "feature"),
            "tenant_id": _to_string(self._options.get("tenant_id")) or _read_string(metadata, "tenant_id"),
            "customer_id": _to_string(self._options.get("customer_id")) or _read_string(metadata, "customer_id"),
            "attempt_type": _to_string(self._options.get("attempt_type")) or _read_string(metadata, "attempt_type"),
            "plan": _to_string(self._options.get("plan")) or _read_string(metadata, "plan"),
            "environment": _to_string(self._options.get("environment")) or _read_string(metadata, "environment"),
            "template_id": _to_string(self._options.get("template_id")) or _read_string(metadata, "template_id"),
            "trace_id": trace_id,
            "run_id": run_id_tag,
            "conversation_id": conversation_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "step_name": step_name,
            "outcome": _to_string(self._options.get("outcome")) or _read_string(metadata, "outcome"),
            "retry_reason": _to_string(self._options.get("retry_reason")) or _read_string(metadata, "retry_reason"),
            "fallback_reason": _to_string(self._options.get("fallback_reason")) or _read_string(
                metadata, "fallback_reason"
            ),
            "quality_label": _to_string(self._options.get("quality_label")) or _read_string(
                metadata, "quality_label"
            ),
            "feedback_score": feedback_score,
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
        evaluation_payload = evaluation if evaluation else None

        self._runs[run_key] = _RunSnapshot(
            started_at=time.time(),
            provider=provider,
            event_type=event_type,
            endpoint=endpoint,
            model=model,
            tags=tags,
            evaluation=evaluation_payload,
        )

    def on_llm_end(self, response: Any, run_id: Any, **kwargs: Any) -> None:
        run_key = str(run_id)
        snapshot = self._runs.pop(run_key, None)
        if snapshot is None:
            self.on_llm_start(serialized={}, prompts=[], run_id=run_key, **kwargs)
            snapshot = self._runs.pop(run_key)

        latency_ms = max(0, int((time.time() - snapshot.started_at) * 1000))
        usage = _extract_usage(response)
        tags = dict(snapshot.tags)
        tags.setdefault("outcome", "success")

        evaluation = dict(snapshot.evaluation or {})
        if evaluation:
            evaluation.setdefault("outcome", tags.get("outcome") or "success")

        payload = {
            "schema_version": "2026-02-16",
            "event_type": snapshot.event_type,
            "provider": snapshot.provider,
            "endpoint": snapshot.endpoint,
            "status": "success",
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "latency_ms": latency_ms,
            "model": snapshot.model or "unknown",
            "usage": usage,
            "tags": tags,
        }
        if evaluation:
            payload["evaluation"] = evaluation

        ingest_event_async(payload, api_key=str(self._options["api_key"]))

    def on_llm_error(self, error: BaseException, run_id: Any, **kwargs: Any) -> None:
        run_key = str(run_id)
        snapshot = self._runs.pop(run_key, None)
        if snapshot is None:
            self.on_llm_start(serialized={}, prompts=[], run_id=run_key, **kwargs)
            snapshot = self._runs.pop(run_key)

        latency_ms = max(0, int((time.time() - snapshot.started_at) * 1000))
        tags = dict(snapshot.tags)
        tags.setdefault("outcome", "failure")

        evaluation = dict(snapshot.evaluation or {})
        if evaluation:
            evaluation.setdefault("outcome", tags.get("outcome") or "failure")

        payload = {
            "schema_version": "2026-02-16",
            "event_type": snapshot.event_type,
            "provider": snapshot.provider,
            "endpoint": snapshot.endpoint,
            "status": "failure",
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "latency_ms": latency_ms,
            "model": snapshot.model or "unknown",
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
        if evaluation:
            payload["evaluation"] = evaluation

        ingest_event_async(payload, api_key=str(self._options["api_key"]))


def create_langchain_callback_handler(**kwargs: Any) -> TokveraLangChainCallbackHandler:
    return TokveraLangChainCallbackHandler(**kwargs)
