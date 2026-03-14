# Changelog

All notable changes to this project will be documented in this file.

## [0.2.8] - 2026-03-14

### Added
- Manual tracing substrate for existing apps:
  - `create_tracer(...)`
  - `start_trace(...)`
  - `start_span(...)`
  - `finish_span(...)`
  - `fail_span(...)`
  - `attach_payload(...)`
  - `get_track_kwargs_from_trace_context(...)`
- Mistral wrapper via `track_mistral(...)`.
- OpenTelemetry bridge via `TokveraOTelSpanExporter`.
- Thin runtime helpers:
  - `configure_claude_agent_sdk(...)`
  - `configure_google_adk(...)`
  - `create_langgraph_tracer(...)`
  - `create_instructor_tracer(...)`
  - `create_pydanticai_tracer(...)`
  - `create_crewai_tracer(...)`
- New examples for manual tracing and agent/runtime helper flows.

### Changed
- Updated SDK user-agent string to `tokvera-python-sdk/0.2.8`.
- Canonical contract expectations now include `mistral.request` and `tokvera.trace`.

## [0.2.7] - 2026-03-14

### Added
- Optional lifecycle start events via `emit_lifecycle_events=True` so Tokvera can show in-progress runs in `/dashboard/traces/live`.

### Changed
- Canonical contract checks now accept `in_progress` as a valid lifecycle status.
- Tracking wrappers reuse generated trace/run/span ids across lifecycle start and terminal events.
- Updated SDK user-agent string to `tokvera-python-sdk/0.2.7`.
- Quickstart and example code now demonstrate realtime trace lifecycle emission.

## [0.2.6] - 2026-03-12

### Added
- Django middleware integration helpers:
  - `create_django_tracking_middleware(...)`
  - `get_django_request_context()`
  - `get_django_track_kwargs(...)`
- Celery task integration helpers:
  - `create_celery_task_context(...)`
  - `get_celery_track_kwargs(...)`
- Adapter integration tests for Django and Celery helper flows.

### Changed
- Updated SDK user-agent string to `tokvera-python-sdk/0.2.6`.

## [0.2.4] - 2026-03-08

### Added
- Background job instrumentation helpers:
  - `create_background_job_context(...)`
  - `get_background_track_kwargs(...)`
- Background worker example for stable trace/run propagation across async steps.

### Changed
- Updated SDK user-agent string to `tokvera-python-sdk/0.2.4`.

## [0.2.3] - 2026-03-07

### Changed
- Ingestion now treats non-2xx API responses as failed deliveries instead of silently succeeding.
- Added retry classification for transient HTTP responses (`408`, `409`, `425`, `429`, `5xx`).
- Async ingestion now emits runtime warnings with HTTP status/details when final delivery fails.
- Updated SDK user-agent string to `tokvera-python-sdk/0.2.3`.

### Added
- New ingest-focused tests covering retryable/non-retryable HTTP failures and async warning behavior.

## [0.2.2] - 2026-03-07

### Added
- FastAPI middleware integration helpers:
  - `create_fastapi_tracking_middleware(...)`
  - `get_fastapi_request_context()`
  - `get_fastapi_track_kwargs(...)`
- LangChain callback integration helpers:
  - `TokveraLangChainCallbackHandler`
  - `create_langchain_callback_handler(...)`
- LlamaIndex callback integration helpers:
  - `TokveraLlamaIndexCallbackHandler`
  - `create_llamaindex_callback_handler(...)`
- Evaluation Signals v1 support in tags and top-level `evaluation` payload fields.

### Changed
- Expanded integration test coverage for framework callbacks and request middleware context propagation.

## [0.2.1] - 2026-03-04

### Added
- Trace Context v1 support in wrapper inputs and emitted tags.
- New optional tags: `trace_id`, `conversation_id`, `span_id`, `parent_span_id`, `step_name`.

### Changed
- Auto-generates `trace_id` and `span_id` per tracked call when not provided.

## [0.2.0] - 2026-03-02

### Added
- Anthropic tracking wrapper via `track_anthropic(...)` for `messages.create`.
- Gemini tracking wrapper via `track_gemini(...)` for `models.generate_content`.
- Multi-provider event contracts aligned with Tokvera API schema.
- Provider-specific usage extraction for OpenAI, Anthropic, and Gemini responses.
- Test coverage for Anthropic/Gemini emission flows.

## [0.1.0] - 2026-02-16

### Added
- OpenAI client wrapper for `chat.completions.create` and `responses.create`.
- Unified event schema with `schema_version`, `endpoint`, `status`, `usage`, and `tags`.
- Authenticated ingestion via `Authorization: Bearer <api_key>`.
- Failure event emission with error metadata while preserving caller exceptions.
- Privacy-safe telemetry defaults with optional prompt/response hashing.
- Tests for success, failure, and non-blocking ingestion behavior.
