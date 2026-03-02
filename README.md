# tokvera

`tokvera` is a lightweight Python SDK that wraps OpenAI, Anthropic, and Gemini clients and emits usage analytics in a fire-and-forget way.

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
- `tags`: `feature`, `tenant_id`, `customer_id`, `plan`, `environment`, `template_id`
- `error` on failure events

## Privacy

By default, prompt/response content is not sent.

If `capture_content=True`, content is hashed (SHA-256) before ingestion. Raw content is never sent by this SDK.

## Disable Tracking

You can disable tracking by either:

1. Using the original OpenAI client directly (do not wrap it), or
2. Unsetting `TOKVERA_INGEST_URL` so no events are emitted.
