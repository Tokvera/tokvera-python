# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-02-16

### Added
- OpenAI client wrapper for `chat.completions.create` and `responses.create`.
- Unified event schema with `schema_version`, `endpoint`, `status`, `usage`, and `tags`.
- Authenticated ingestion via `Authorization: Bearer <api_key>`.
- Failure event emission with error metadata while preserving caller exceptions.
- Privacy-safe telemetry defaults with optional prompt/response hashing.
- Tests for success, failure, and non-blocking ingestion behavior.
