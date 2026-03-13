# tokvera

Python SDK for Tokvera AI cost and trace telemetry.

Current version: `0.2.6`

## What It Tracks

- OpenAI
- Anthropic
- Gemini

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
)

tracked.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
)
```

Set ingest URL:

```bash
export TOKVERA_INGEST_URL="https://api.tokvera.org/v1/events"
```

## Integration Helpers

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

- `examples/fastapi_middleware.py`
- `examples/django_middleware.py`
- `examples/background_jobs.py`
- `examples/celery_task.py`

## Test

```bash
pytest
```
