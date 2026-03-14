# tokvera

Python SDK for Tokvera AI cost and trace telemetry.

Current version: `0.2.9`

## What It Tracks

- OpenAI
- Anthropic
- Gemini
- Mistral

Tracked calls emit normalized telemetry to Tokvera ingest (`/v1/events`) with:
- latency, status, model, token usage
- trace context (`trace_id`, `run_id`, `span_id`, `parent_span_id`, `conversation_id`)
- evaluation signals (`outcome`, `retry_reason`, `fallback_reason`, `quality_label`, `feedback_score`)
- optional v2 trace fields (span/tool metadata, payload refs/blocks, per-step metrics, routing decisions)

## Install

```bash
pip install tokvera
```

For local development:

```bash
pip install -e .[dev]
```

## Quick Start

```python
from openai import OpenAI
from tokvera import track_openai

openai_client = OpenAI(api_key="sk-...")

tracked = track_openai(
    openai_client,
    api_key="tkv_project_key",
    feature="support_bot",
    tenant_id="acme",
    environment="production",
    step_name="draft_reply",
    emit_lifecycle_events=True,
)

tracked.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
)
```

Enable `emit_lifecycle_events=True` when you want `/dashboard/traces/live` to show a run immediately at call start and keep it marked as processing until the terminal event lands.

Set ingest URL:

```bash
export TOKVERA_INGEST_URL="https://api.tokvera.org/v1/events"
```

## Integration Helpers

- Existing app / manual tracing:
  - `create_tracer(...)`
  - `start_trace(...)`
  - `start_span(...)`
  - `finish_span(...)`
  - `fail_span(...)`
  - `attach_payload(...)`
  - `get_track_kwargs_from_trace_context(...)`
- Mistral:
  - `track_mistral(...)`
- Claude Agent SDK:
  - `configure_claude_agent_sdk(...)`
- Google ADK:
  - `configure_google_adk(...)`
- LangGraph:
  - `create_langgraph_tracer(...)`
- Instructor:
  - `create_instructor_tracer(...)`
- PydanticAI:
  - `create_pydanticai_tracer(...)`
- CrewAI:
  - `create_crewai_tracer(...)`
- Wave 2 beta runtimes:
  - `create_autogen_tracer(...)`
  - `create_mastra_tracer(...)`
  - `create_temporal_tracer(...)`
  - `create_pipecat_tracer(...)`
  - `create_livekit_tracer(...)`
  - `create_openai_compatible_gateway_tracer(...)`
- OpenTelemetry bridge:
  - `TokveraOTelSpanExporter`
- FastAPI middleware:
  - `create_fastapi_tracking_middleware(...)`
  - `get_fastapi_track_kwargs(...)`
- Django middleware:
  - `create_django_tracking_middleware(...)`
  - `get_django_track_kwargs(...)`
- Background jobs:
  - `create_background_job_context(...)`
  - `get_background_track_kwargs(...)`
- Celery:
  - `create_celery_task_context(...)`
  - `get_celery_track_kwargs(...)`
- LangChain:
  - `create_langchain_callback_handler(...)`
- LlamaIndex:
  - `create_llamaindex_callback_handler(...)`

## Trace Schema Support

- v1 schema version: `2026-02-16`
- v2 schema version: `2026-04-01`

Contract references:
- `tokvera-api/docs/event-envelope-v1.contract.json`
- `tokvera-api/docs/event-envelope-v2.contract.json`
- `tokvera-api/docs/SCHEMA_COMPATIBILITY_POLICY.md`

## Privacy Behavior

- Tracking is fire-and-forget and non-blocking
- Prompt/output content is not required
- If v2 content capture is enabled, payload hashes/blocks are included based on options

## Examples

- `examples/manual_tracer.py`
- `examples/agent_runtimes.py`
- `examples/beta_runtime_helpers.py`
- `examples/fastapi_middleware.py`
- `examples/django_middleware.py`
- `examples/background_jobs.py`
- `examples/celery_task.py`

## Realtime Tracing

- `/dashboard/traces` is the main engineering workspace for execution, payload, and optimization debugging.
- `/dashboard/traces/live` is the realtime feed for active and recently completed runs.
- Lifecycle start events are additive. They do not replace the normal terminal success/failure event.

## Test

```bash
pytest
```
