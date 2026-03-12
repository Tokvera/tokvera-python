from __future__ import annotations

from typing import Any

from tokvera.integrations.django import (
    create_django_tracking_middleware,
    get_django_request_context,
    get_django_track_kwargs,
)


class _Request:
    def __init__(self, *, meta: dict[str, str], method: str, path: str) -> None:
        self.META = meta
        self.method = method
        self.path = path


class _Response:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}

    def __setitem__(self, key: str, value: str) -> None:
        self.headers[key] = value


def test_django_middleware_sets_context_and_response_header() -> None:
    captured: dict[str, Any] = {}

    middleware_factory = create_django_tracking_middleware(
        defaults={
            "feature": "support_bot",
            "tenant_id": "acme",
            "environment": "production",
        },
        context_resolver=lambda _: {
            "customer_id": "cust_1",
            "outcome": "success",
            "quality_label": "good",
            "feedback_score": "4.5",
        },
    )

    request = _Request(
        meta={
            "HTTP_X_TOKVERA_TRACE_ID": "trc_from_header",
            "HTTP_X_TOKVERA_RUN_ID": "run_from_header",
        },
        method="POST",
        path="/reply",
    )

    def get_response(_: Any) -> _Response:
        request_context = get_django_request_context()
        captured.update(request_context)
        track_kwargs = get_django_track_kwargs(step_name="draft_reply")
        captured["track_kwargs"] = track_kwargs
        return _Response()

    middleware = middleware_factory(get_response)
    response = middleware(request)

    assert captured["trace_id"] == "trc_from_header"
    assert captured["run_id"] == "run_from_header"
    assert captured["feature"] == "support_bot"
    assert captured["tenant_id"] == "acme"
    assert captured["customer_id"] == "cust_1"
    assert captured["step_name"] == "post /reply"
    assert captured["feedback_score"] == 4.5
    assert captured["track_kwargs"]["parent_span_id"] == captured["span_id"]
    assert captured["track_kwargs"]["span_id"] != captured["span_id"]
    assert captured["track_kwargs"]["step_name"] == "draft_reply"
    assert response.headers["x-tokvera-trace-id"] == "trc_from_header"

    assert get_django_request_context() == {}


def test_django_middleware_generates_trace_when_missing_header() -> None:
    middleware_factory = create_django_tracking_middleware(
        defaults={"feature": "assistant"}
    )
    request = _Request(meta={}, method="GET", path="/health")

    def get_response(_: Any) -> _Response:
        context = get_django_request_context()
        assert context["feature"] == "assistant"
        assert context["step_name"] == "get /health"
        assert context["trace_id"].startswith("trc_")
        assert context["span_id"].startswith("spn_")
        return _Response()

    middleware = middleware_factory(get_response)
    response = middleware(request)
    assert response.headers["x-tokvera-trace-id"].startswith("trc_")

