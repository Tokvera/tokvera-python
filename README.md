# tokvera

`tokvera` is a lightweight Python SDK that wraps the official OpenAI client and emits usage analytics in a fire-and-forget way.

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
export TOKVERA_INGEST_URL="https://your-ingest-endpoint/v1/events"

# Windows PowerShell
$env:TOKVERA_INGEST_URL = "https://your-ingest-endpoint/v1/events"
```

If `TOKVERA_INGEST_URL` is not set, analytics are skipped automatically.

## Quick Start

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

## Event Schema

Events include:
- `schema_version`: `2026-02-16`
- `event_type`: `openai.request`
- `provider`: `openai`
- `endpoint`: `chat.completions.create` or `responses.create`
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
