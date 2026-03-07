from __future__ import annotations

import asyncio
from typing import Any

from tokvera.integrations.fastapi import (
    create_fastapi_tracking_middleware,
    get_fastapi_request_context,
    get_fastapi_track_kwargs,
)


class _Headers(dict[str, str]):
    def get(self, key: str, default: Any = None) -> Any:
        for header_key, value in self.items():
            if header_key.lower() == key.lower():
                return value
        return default


class _URL:
    def __init__(self, path: str) -> None:
        self.path = path


class _Request:
    def __init__(self, *, headers: dict[str, str], method: str, path: str) -> None:
        self.headers = _Headers(headers)
        self.method = method
        self.url = _URL(path)


class _Response:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}


def test_fastapi_middleware_sets_request_context_and_response_header() -> None:
    captured: dict[str, Any] = {}

    middleware = create_fastapi_tracking_middleware(
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
        headers={
            "x-tokvera-trace-id": "trc_from_header",
            "x-tokvera-run-id": "run_from_header",
        },
        method="POST",
        path="/reply",
    )

    async def call_next(_: Any) -> _Response:
        request_context = get_fastapi_request_context()
        captured.update(request_context)
        track_kwargs = get_fastapi_track_kwargs(step_name="draft_reply")
        captured["track_kwargs"] = track_kwargs
        return _Response()

    response = asyncio.run(middleware(request, call_next))

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

    assert get_fastapi_request_context() == {}


def test_fastapi_middleware_generates_trace_when_missing_header() -> None:
    middleware = create_fastapi_tracking_middleware(
        defaults={"feature": "assistant"}
    )
    request = _Request(headers={}, method="GET", path="/health")

    async def call_next(_: Any) -> _Response:
        context = get_fastapi_request_context()
        assert context["feature"] == "assistant"
        assert context["step_name"] == "get /health"
        assert context["trace_id"].startswith("trc_")
        assert context["span_id"].startswith("spn_")
        return _Response()

    response = asyncio.run(middleware(request, call_next))
    assert response.headers["x-tokvera-trace-id"].startswith("trc_")
