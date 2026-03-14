from openai import OpenAI

from tokvera import (
    create_tracer,
    finish_span,
    get_track_kwargs_from_trace_context,
    start_span,
    start_trace,
    track_openai,
)

tracer = create_tracer(
    api_key="tkv_project_key",
    feature="custom_router",
    tenant_id="acme",
    environment="production",
    emit_lifecycle_events=True,
)

root = start_trace(tracer, step_name="handle_request", model="custom-router", span_kind="orchestrator")
classify = start_span(root, step_name="classify_intent", provider="openai", model="gpt-4o-mini", span_kind="model")

client = track_openai(
    OpenAI(api_key="sk-..."),
    **get_track_kwargs_from_trace_context(
        classify,
        step_name="classify_intent",
        span_kind="model",
        capture_content=True,
    ),
)

result = client.responses.create(model="gpt-4o-mini", input="Classify this billing request.")

finish_span(classify, response=result, model="gpt-4o-mini")
finish_span(root, response={"routed_to": "billing"})
