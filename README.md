# tokvera

`tokvera` is a lightweight Python SDK that wraps OpenAI, Anthropic, and Gemini clients and emits usage analytics in a fire-and-forget way.

## What's New in v0.2.2

- Added Trace Context v1 tags.
- New optional tags: `trace_id`, `run_id`, `conversation_id`, `span_id`, `parent_span_id`, `step_name`.
- Added Evaluation Signals v1 fields: `outcome`, `retry_reason`, `fallback_reason`, `quality_label`, `feedback_score`.
- Added FastAPI middleware integration helpers.
- Added LangChain callback integration helpers.
- Added LlamaIndex callback integration helpers.
- Auto-generates `trace_id` and `span_id` when you do not provide them.

## Installation

```bash
pip install tokvera
```

For development:

```bash
pip install -e .[dev]
```

## Environment Variable Setup

Set your ingestion endpoint:

```bash
# Linux/macOS
export TOKVERA_INGEST_URL="https://api.tokvera.com/v1/events"

# Windows PowerShell
$env:TOKVERA_INGEST_URL = "https://api.tokvera.com/v1/events"
```

If `TOKVERA_INGEST_URL` is not set, analytics are skipped automatically.

## Trace Context v1

Use trace tags to reconstruct request chains without sending prompt payloads.

Recommended semantics:
- `trace_id`: one end-to-end workflow/request.
- `run_id`: one execution run of an agent/workflow.
- `conversation_id`: one user conversation/session.
- `span_id`: one model call.
- `parent_span_id`: parent model call when nested.
- `step_name`: readable stage label (`retrieve_context`, `draft_reply`, `quality_retry`).

Example:

```python
client = track_openai(
    openai_client,
    api_key="tokvera_project_key",
    feature="support_bot",
    tenant_id="acme",
    trace_id="trace_req_20260304_001",
    run_id="run_agent_20260304_001",
    conversation_id="conv_9832",
    span_id="span_root_1",
    parent_span_id=None,
    step_name="draft_reply",
)
```

## FastAPI Middleware Integration

Use middleware to create request-level trace context and pass it into SDK calls.

```python
from fastapi import FastAPI, Request
from openai import OpenAI
from tokvera import (
    create_fastapi_tracking_middleware,
    get_fastapi_track_kwargs,
    track_openai,
)

app = FastAPI()
openai_client = OpenAI(api_key="sk-...")

middleware = create_fastapi_tracking_middleware(
    defaults={"feature": "support_bot", "environment": "production"},
    context_resolver=lambda request: {"tenant_id": request.headers.get("x-tenant-id")},
)

@app.middleware("http")
async def tokvera_context(request: Request, call_next):
    return await middleware(request, call_next)

@app.post("/reply")
async def reply():
    tracked = track_openai(
        openai_client,
        api_key="tokvera_project_key",
        **get_fastapi_track_kwargs(step_name="draft_reply"),
    )
    return tracked.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
    )
```

## LangChain Callback Integration

Use a callback handler to emit Tokvera events from LangChain LLM runs.

```python
from langchain_openai import ChatOpenAI
from tokvera import create_langchain_callback_handler

callback = create_langchain_callback_handler(
    api_key="tokvera_project_key",
    feature="agent_support",
    tenant_id="acme",
    environment="production",
)

model = ChatOpenAI(
    model="gpt-4o-mini",
    callbacks=[callback],
)

result = model.invoke("Hello")
```

## LlamaIndex Callback Integration

Use a callback handler to emit Tokvera events from LlamaIndex workflows.

```python
from llama_index.core.callbacks import CallbackManager
from tokvera import create_llamaindex_callback_handler

tokvera_handler = create_llamaindex_callback_handler(
    api_key="tokvera_project_key",
    feature="agent_support",
    tenant_id="acme",
    environment="production",
)

callback_manager = CallbackManager([tokvera_handler])
```

## Quick Start

### OpenAI

```python
from openai import OpenAI
from tokvera import track_openai

openai_client = OpenAI(api_key="sk-...")

client = track_openai(
    openai_client,
    api_key="tokvera_project_key",
    feature="support_bot",
    tenant_id="acme",
    trace_id="trace_support_001",
    run_id="run_support_001",
    conversation_id="conv_42",
    step_name="draft_reply",
    outcome="success",
    quality_label="good",
    feedback_score=5,
    plan="pro",
    environment="production",
    template_id="support_v3",
    capture_content=False,
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
)
```

### Anthropic

```python
from anthropic import Anthropic
from tokvera import track_anthropic

anthropic_client = Anthropic(api_key="sk-ant-...")

client = track_anthropic(
    anthropic_client,
    api_key="tokvera_project_key",
    feature="support_bot",
    tenant_id="acme",
    environment="production",
)

client.messages.create(
    model="claude-3-5-sonnet-latest",
    max_tokens=256,
    messages=[{"role": "user", "content": "Hello"}],
)
```

### Gemini

```python
from google import genai
from tokvera import track_gemini

gemini_client = genai.Client(api_key="AIza...")

client = track_gemini(
    gemini_client,
    api_key="tokvera_project_key",
    feature="assistant",
    tenant_id="acme",
    environment="production",
)

client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Hello",
)
```

## Event Schema

Canonical specification: [`tokvera-api/docs/EVENT_SCHEMA.md`](https://github.com/Tokvera/tokvera-api/blob/main/docs/EVENT_SCHEMA.md)

Events include:
- `schema_version`: `2026-02-16`
- `event_type`: `openai.request`, `anthropic.request`, or `gemini.request`
- `provider`: `openai`, `anthropic`, or `gemini`
- `endpoint`: `chat.completions.create`, `responses.create`, `messages.create`, `models.generate_content`
- `status`: `success` or `failure`
- `latency_ms`
- `model`
- `usage`: `prompt_tokens`, `completion_tokens`, `total_tokens`
- `tags`: `feature`, `tenant_id`, `customer_id`, `attempt_type`, `plan`, `environment`, `template_id`, `trace_id`, `run_id`, `conversation_id`, `span_id`, `parent_span_id`, `step_name`
- Evaluation signals (optional): `outcome`, `retry_reason`, `fallback_reason`, `quality_label`, `feedback_score` (emitted in `tags` and top-level `evaluation`)
- `error` on failure events

`trace_id` and `span_id` are auto-generated per request if not provided.

## Privacy

By default, prompt/response content is not sent.

If `capture_content=True`, content is hashed (SHA-256) before ingestion. Raw content is never sent by this SDK.

## Disable Tracking

You can disable tracking by either:

1. Using the original OpenAI client directly (do not wrap it), or
2. Unsetting `TOKVERA_INGEST_URL` so no events are emitted.
