from __future__ import annotations

import uuid
from typing import Any, Dict, Mapping, Optional


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _tag_value(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def _feedback_score(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _compact(values: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def create_background_job_context(
    *,
    job_id: Optional[str] = None,
    feature: Optional[str] = None,
    tenant_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    attempt_type: Optional[str] = None,
    plan: Optional[str] = None,
    environment: Optional[str] = None,
    template_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    root_span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    step_name: Optional[str] = None,
    outcome: Optional[str] = None,
    retry_reason: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    quality_label: Optional[str] = None,
    feedback_score: Optional[float] = None,
) -> Dict[str, Any]:
    normalized_trace_id = _tag_value(trace_id) or _new_id("trc")
    normalized_run_id = _tag_value(run_id) or _new_id("run")
    normalized_root_span_id = _tag_value(root_span_id) or _new_id("spn")

    base_track_kwargs = _compact(
        {
            "feature": _tag_value(feature),
            "tenant_id": _tag_value(tenant_id),
            "customer_id": _tag_value(customer_id),
            "attempt_type": _tag_value(attempt_type),
            "plan": _tag_value(plan),
            "environment": _tag_value(environment),
            "template_id": _tag_value(template_id),
            "trace_id": normalized_trace_id,
            "run_id": normalized_run_id,
            "conversation_id": _tag_value(conversation_id),
            "span_id": normalized_root_span_id,
            "parent_span_id": _tag_value(parent_span_id),
            "step_name": _tag_value(step_name),
            "outcome": _tag_value(outcome),
            "retry_reason": _tag_value(retry_reason),
            "fallback_reason": _tag_value(fallback_reason),
            "quality_label": _tag_value(quality_label),
            "feedback_score": _feedback_score(feedback_score),
        }
    )

    return {
        "job_id": _tag_value(job_id),
        "trace_id": normalized_trace_id,
        "run_id": normalized_run_id,
        "conversation_id": _tag_value(conversation_id),
        "root_span_id": normalized_root_span_id,
        "base_track_kwargs": base_track_kwargs,
    }


def get_background_track_kwargs(
    context: Mapping[str, Any],
    **overrides: Any,
) -> Dict[str, Any]:
    base = dict(context.get("base_track_kwargs") or {})

    trace_id = (
        _tag_value(overrides.get("trace_id"))
        or _tag_value(context.get("trace_id"))
        or _tag_value(base.get("trace_id"))
        or _new_id("trc")
    )
    run_id = (
        _tag_value(overrides.get("run_id"))
        or _tag_value(context.get("run_id"))
        or _tag_value(base.get("run_id"))
        or _new_id("run")
    )
    parent_span_id = (
        _tag_value(overrides.get("parent_span_id"))
        or _tag_value(context.get("root_span_id"))
        or _tag_value(base.get("span_id"))
    )
    span_id = _tag_value(overrides.get("span_id")) or _new_id("spn")

    merged = {
        **base,
        **overrides,
        "trace_id": trace_id,
        "run_id": run_id,
        "conversation_id": (
            _tag_value(overrides.get("conversation_id"))
            or _tag_value(context.get("conversation_id"))
            or _tag_value(base.get("conversation_id"))
        ),
        "span_id": span_id,
        "parent_span_id": parent_span_id,
    }

    if "feedback_score" in merged:
        merged["feedback_score"] = _feedback_score(merged.get("feedback_score"))

    return _compact(merged)

