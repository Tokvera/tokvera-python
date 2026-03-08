from tokvera.integrations.background import (
    create_background_job_context,
    get_background_track_kwargs,
)


def test_background_context_generates_trace_run_and_root_span() -> None:
    context = create_background_job_context(
        job_id="job_123",
        feature="daily_summary",
        tenant_id="acme",
        environment="production",
    )

    assert context["job_id"] == "job_123"
    assert context["trace_id"].startswith("trc_")
    assert context["run_id"].startswith("run_")
    assert context["root_span_id"].startswith("spn_")
    assert context["base_track_kwargs"]["feature"] == "daily_summary"
    assert context["base_track_kwargs"]["tenant_id"] == "acme"
    assert context["base_track_kwargs"]["trace_id"] == context["trace_id"]
    assert context["base_track_kwargs"]["run_id"] == context["run_id"]
    assert context["base_track_kwargs"]["span_id"] == context["root_span_id"]


def test_background_track_kwargs_create_child_span_with_parent_link() -> None:
    context = create_background_job_context(
        trace_id="trc_batch_001",
        run_id="run_batch_001",
        root_span_id="spn_batch_root",
        feature="billing_backfill",
        tenant_id="acme",
    )

    kwargs = get_background_track_kwargs(
        context,
        step_name="aggregate_hourly",
        quality_label="good",
        feedback_score="4.5",
    )

    assert kwargs["trace_id"] == "trc_batch_001"
    assert kwargs["run_id"] == "run_batch_001"
    assert kwargs["parent_span_id"] == "spn_batch_root"
    assert kwargs["feature"] == "billing_backfill"
    assert kwargs["step_name"] == "aggregate_hourly"
    assert kwargs["quality_label"] == "good"
    assert kwargs["feedback_score"] == 4.5
    assert kwargs["span_id"].startswith("spn_")
    assert kwargs["span_id"] != "spn_batch_root"

