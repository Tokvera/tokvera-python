from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any, Callable, Mapping, Optional

_DJANGO_REQUEST_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar(
    "tokvera_django_request_context",
    default=None,
)

_STRING_CONTEXT_KEYS = {
    "api_key",
    "feature",
    "tenant_id",
    "customer_id",
    "attempt_type",
    "plan",
    "environment",
    "template_id",
    "trace_id",
    "run_id",
    "conversation_id",
    "span_id",
    "parent_span_id",
    "step_name",
    "outcome",
    "retry_reason",
    "fallback_reason",
    "quality_label",
}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _to_non_empty_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    text = str(value).strip()
    return text or None


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _read_meta(request: Any, key: str) -> Optional[str]:
    meta = getattr(request, "META", None)
    if not isinstance(meta, Mapping):
        return None
    return _to_non_empty_string(meta.get(key))


def _derive_step_name(request: Any) -> Optional[str]:
    method = _to_non_empty_string(getattr(request, "method", None))
    path = _to_non_empty_string(getattr(request, "path", None))
    if path is None:
        return None
    if method is None:
        return path
    return f"{method.lower()} {path}"


def _normalize_context(values: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in values.items():
        if key == "feedback_score":
            score = _to_optional_float(value)
            if score is not None:
                normalized[key] = score
            continue

        if key in _STRING_CONTEXT_KEYS:
            text = _to_non_empty_string(value)
            if text is not None:
                normalized[key] = text
            continue

        if value is not None:
            normalized[key] = value

    return normalized


def create_django_tracking_middleware(
    *,
    defaults: Optional[Mapping[str, Any]] = None,
    context_resolver: Optional[Callable[[Any], Mapping[str, Any]]] = None,
    trace_meta_key: str = "HTTP_X_TOKVERA_TRACE_ID",
    run_meta_key: str = "HTTP_X_TOKVERA_RUN_ID",
    conversation_meta_key: str = "HTTP_X_TOKVERA_CONVERSATION_ID",
    response_trace_header: str = "x-tokvera-trace-id",
) -> Callable[[Callable[[Any], Any]], Callable[[Any], Any]]:
    base_defaults = dict(defaults or {})

    def middleware_factory(get_response: Callable[[Any], Any]) -> Callable[[Any], Any]:
        def middleware(request: Any) -> Any:
            resolved: dict[str, Any] = dict(base_defaults)
            if context_resolver is not None:
                resolved_from_request = dict(context_resolver(request) or {})
                resolved.update(resolved_from_request)

            trace_id = (
                _read_meta(request, trace_meta_key)
                or _to_non_empty_string(resolved.get("trace_id"))
                or _new_id("trc")
            )
            run_id = _read_meta(request, run_meta_key) or _to_non_empty_string(resolved.get("run_id"))
            conversation_id = _read_meta(request, conversation_meta_key) or _to_non_empty_string(
                resolved.get("conversation_id")
            )
            step_name = _to_non_empty_string(resolved.get("step_name")) or _derive_step_name(request)

            request_context = _normalize_context(
                {
                    **resolved,
                    "trace_id": trace_id,
                    "run_id": run_id,
                    "conversation_id": conversation_id,
                    "span_id": _new_id("spn"),
                    "step_name": step_name,
                }
            )

            setattr(request, "tokvera", request_context)
            token = _DJANGO_REQUEST_CONTEXT.set(request_context)
            try:
                response = get_response(request)
            finally:
                _DJANGO_REQUEST_CONTEXT.reset(token)

            if response is not None:
                headers = getattr(response, "headers", None)
                if isinstance(headers, Mapping):
                    setter = getattr(headers, "__setitem__", None)
                    if callable(setter):
                        setter(response_trace_header, trace_id)
                else:
                    setter = getattr(response, "__setitem__", None)
                    if callable(setter):
                        try:
                            setter(response_trace_header, trace_id)
                        except Exception:
                            pass

            return response

        return middleware

    return middleware_factory


def get_django_request_context() -> dict[str, Any]:
    context = _DJANGO_REQUEST_CONTEXT.get()
    return dict(context or {})


def get_django_track_kwargs(**overrides: Any) -> dict[str, Any]:
    context = get_django_request_context()
    merged = {**context, **overrides}

    if "trace_id" not in merged:
        merged["trace_id"] = _new_id("trc")

    if overrides.get("parent_span_id") is None:
        request_span_id = _to_non_empty_string(context.get("span_id"))
        if request_span_id is not None:
            merged["parent_span_id"] = request_span_id

    if overrides.get("span_id") is None:
        merged["span_id"] = _new_id("spn")

    return _normalize_context(merged)

