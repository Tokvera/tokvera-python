from __future__ import annotations

from tokvera.integrations.celery import (
    create_celery_task_context,
    get_celery_track_kwargs,
)


class _TaskRequest:
    def __init__(
        self,
        *,
        id: str,
        root_id: str,
        parent_id: str,
        task: str,
        retries: int,
        headers: dict[str, str],
    ) -> None:
        self.id = id
        self.root_id = root_id
        self.parent_id = parent_id
        self.task = task
        self.retries = retries
        self.headers = headers


def test_celery_context_uses_request_headers_and_retry_state() -> None:
    request = _TaskRequest(
        id="task_100",
        root_id="trc_root_100",
        parent_id="spn_parent_100",
        task="sync_usage",
        retries=1,
        headers={
            "x-tokvera-trace-id": "trc_header_100",
            "x-tokvera-run-id": "run_header_100",
            "x-tokvera-conversation-id": "conv_header_100",
        },
    )

    context = create_celery_task_context(
        request,
        tenant_id="acme",
        environment="production",
    )

    assert context["job_id"] == "task_100"
    assert context["trace_id"] == "trc_header_100"
    assert context["run_id"] == "run_header_100"
    assert context["conversation_id"] == "conv_header_100"
    assert context["base_track_kwargs"]["feature"] == "sync_usage"
    assert context["base_track_kwargs"]["attempt_type"] == "retry"

    kwargs = get_celery_track_kwargs(
        context,
        step_name="worker_model_call",
    )
    assert kwargs["trace_id"] == "trc_header_100"
    assert kwargs["run_id"] == "run_header_100"
    assert kwargs["parent_span_id"] == context["root_span_id"]
    assert kwargs["step_name"] == "worker_model_call"
    assert kwargs["span_id"].startswith("spn_")


def test_celery_context_falls_back_to_task_root_and_generates_missing_ids() -> None:
    request = _TaskRequest(
        id="task_200",
        root_id="root_200",
        parent_id="parent_200",
        task="nightly_summary",
        retries=0,
        headers={},
    )

    context = create_celery_task_context(
        request,
        tenant_id="acme",
    )
    assert context["trace_id"] == "root_200"
    assert context["run_id"] == "task_200"
    assert context["base_track_kwargs"]["attempt_type"] == "initial"

