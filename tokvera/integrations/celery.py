from __future__ import annotations

from typing import Any, Mapping, Optional

from .background import create_background_job_context, get_background_track_kwargs


def _to_non_empty_string(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def _read_header(headers: Mapping[str, Any], name: str) -> Optional[str]:
    lower_name = name.lower()
    for key, value in headers.items():
        if str(key).lower() != lower_name:
            continue
        return _to_non_empty_string(value)
    return None


def create_celery_task_context(
    task_request: Any = None,
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
) -> dict[str, Any]:
    request_headers = getattr(task_request, "headers", None)
    headers = request_headers if isinstance(request_headers, Mapping) else {}

    task_id = _to_non_empty_string(getattr(task_request, "id", None))
    task_root_id = _to_non_empty_string(getattr(task_request, "root_id", None))
    task_parent_id = _to_non_empty_string(getattr(task_request, "parent_id", None))
    task_name = _to_non_empty_string(getattr(task_request, "task", None))
    retries = getattr(task_request, "retries", 0)
    try:
        retries_count = int(retries)
    except (TypeError, ValueError):
        retries_count = 0

    normalized_trace_id = (
        _to_non_empty_string(trace_id)
        or _read_header(headers, "x-tokvera-trace-id")
        or _read_header(headers, "trace_id")
        or task_root_id
    )
    normalized_run_id = (
        _to_non_empty_string(run_id)
        or _read_header(headers, "x-tokvera-run-id")
        or _read_header(headers, "run_id")
        or task_id
    )
    normalized_conversation_id = (
        _to_non_empty_string(conversation_id)
        or _read_header(headers, "x-tokvera-conversation-id")
        or _read_header(headers, "conversation_id")
    )
    normalized_parent_span_id = (
        _to_non_empty_string(parent_span_id)
        or _read_header(headers, "x-tokvera-parent-span-id")
        or _read_header(headers, "parent_span_id")
        or task_parent_id
    )

    return create_background_job_context(
        job_id=_to_non_empty_string(job_id) or task_id,
        feature=_to_non_empty_string(feature) or task_name,
        tenant_id=tenant_id,
        customer_id=customer_id,
        attempt_type=_to_non_empty_string(attempt_type) or ("retry" if retries_count > 0 else "initial"),
        plan=plan,
        environment=environment,
        template_id=template_id,
        trace_id=normalized_trace_id,
        run_id=normalized_run_id,
        conversation_id=normalized_conversation_id,
        root_span_id=root_span_id,
        parent_span_id=normalized_parent_span_id,
        step_name=step_name,
        outcome=outcome,
        retry_reason=retry_reason,
        fallback_reason=fallback_reason,
        quality_label=quality_label,
        feedback_score=feedback_score,
    )


def get_celery_track_kwargs(context: Mapping[str, Any], **overrides: Any) -> dict[str, Any]:
    return get_background_track_kwargs(context, **overrides)

