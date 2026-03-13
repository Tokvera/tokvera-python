from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "https://api.tokvera.org"

REQUIRED_TOP_LEVEL_FIELDS = [
    "schema_version",
    "event_type",
    "provider",
    "endpoint",
    "status",
    "timestamp",
    "latency_ms",
    "model",
    "usage",
    "tags",
]
STATUS_VALUES = ["in_progress", "success", "failure"]
USAGE_FIELDS = ["prompt_tokens", "completion_tokens", "total_tokens"]
ERROR_FIELDS = ["type", "message"]
ALLOWED_TAG_FIELDS = [
    "feature",
    "tenant_id",
    "customer_id",
    "attempt_type",
    "plan",
    "environment",
    "template_id",
    "trace_id",
    "run_id",
    "conversation_id",
    "span_id",
    "parent_span_id",
    "step_name",
    "outcome",
    "retry_reason",
    "fallback_reason",
    "quality_label",
    "feedback_score",
]
EVALUATION_FIELDS = [
    "outcome",
    "retry_reason",
    "fallback_reason",
    "quality_label",
    "feedback_score",
]
PROVIDER_CONTRACTS = {
    "openai": {
        "event_type": "openai.request",
        "endpoints": ["chat.completions.create", "responses.create"],
    },
    "anthropic": {
        "event_type": "anthropic.request",
        "endpoints": ["messages.create"],
    },
    "gemini": {
        "event_type": "gemini.request",
        "endpoints": ["models.generate_content"],
    },
}
STRICT_VALIDATION = {
    "allow_unknown_top_level_fields": False,
    "allow_unknown_usage_fields": False,
    "allow_unknown_tag_fields": False,
    "allow_unknown_evaluation_fields": False,
    "allow_unknown_error_fields": False,
}
COMPATIBILITY_POLICY = {
    "additive_optional_fields": True,
    "required_fields_require_schema_bump": True,
    "semantic_changes_require_schema_bump": True,
    "deprecations_require_staged_rollout": True,
}

EXPECTED_V1 = {
    "envelope_version": "v1",
    "schema_version": "2026-02-16",
    "optional_top_level_fields": ["prompt_hash", "response_hash", "error", "evaluation"],
    "validation_error_codes": [
        "MISSING_FIELD",
        "UNSUPPORTED_VERSION",
        "UNSUPPORTED_EVENT_TYPE",
        "INVALID_SCHEMA",
        "UNKNOWN_TOP_LEVEL_FIELD",
        "UNKNOWN_USAGE_FIELD",
        "UNKNOWN_TAG_FIELD",
        "UNKNOWN_EVALUATION_FIELD",
        "UNKNOWN_ERROR_FIELD",
    ],
}

EXPECTED_V2 = {
    "envelope_version": "v2",
    "schema_version": "2026-04-01",
    "optional_top_level_fields": [
        "prompt_hash",
        "response_hash",
        "error",
        "evaluation",
        "span_kind",
        "tool_name",
        "payload_refs",
        "payload_blocks",
        "metrics",
        "decision",
    ],
    "validation_error_codes": [
        "MISSING_FIELD",
        "UNSUPPORTED_VERSION",
        "UNSUPPORTED_EVENT_TYPE",
        "INVALID_SCHEMA",
        "UNKNOWN_TOP_LEVEL_FIELD",
        "UNKNOWN_USAGE_FIELD",
        "UNKNOWN_TAG_FIELD",
        "UNKNOWN_EVALUATION_FIELD",
        "UNKNOWN_ERROR_FIELD",
        "UNKNOWN_METRICS_FIELD",
        "UNKNOWN_DECISION_FIELD",
    ],
    "span_kinds": ["model", "tool", "orchestrator", "retrieval", "guardrail"],
    "payload_types": ["prompt_input", "tool_input", "tool_output", "model_output", "context", "other"],
    "metrics_fields": ["prompt_tokens", "completion_tokens", "total_tokens", "latency_ms", "cost_usd"],
    "decision_fields": ["outcome", "retry_reason", "fallback_reason", "routing_reason", "route"],
}


def as_sorted_set(values: list[str]) -> list[str]:
    return sorted(set(values))


def assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{label} mismatch. expected={expected} actual={actual}")


def assert_set_equal(actual: list[str], expected: list[str], label: str) -> None:
    actual_sorted = as_sorted_set(actual)
    expected_sorted = as_sorted_set(expected)
    if actual_sorted != expected_sorted:
        raise RuntimeError(
            f"{label} mismatch.\nexpected={json.dumps(expected_sorted)}\nactual={json.dumps(actual_sorted)}"
        )


def fetch_schema(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url=url,
        method="GET",
        headers={
            "User-Agent": "tokvera-python-ci-contract-check/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Canonical contract request failed for {url}: {exc}") from exc

    if not payload.get("ok") or not isinstance(payload.get("schema"), dict):
        raise RuntimeError(f"Canonical contract response payload format is invalid for {url}.")

    return payload["schema"]


def assert_common_schema(schema: dict[str, Any], *, v2: bool) -> None:
    assert_set_equal(schema.get("required_top_level_fields", []), REQUIRED_TOP_LEVEL_FIELDS, "required_top_level_fields")
    assert_set_equal(schema.get("status_values", []), STATUS_VALUES, "status_values")
    assert_set_equal(schema.get("usage_fields", []), USAGE_FIELDS, "usage_fields")
    assert_set_equal(schema.get("error_fields", []), ERROR_FIELDS, "error_fields")
    assert_set_equal(schema.get("allowed_tag_fields", []), ALLOWED_TAG_FIELDS, "allowed_tag_fields")
    assert_set_equal(schema.get("evaluation_fields", []), EVALUATION_FIELDS, "evaluation_fields")
    assert_set_equal(
        schema.get("validation_error_codes", []),
        EXPECTED_V2["validation_error_codes"] if v2 else EXPECTED_V1["validation_error_codes"],
        "validation_error_codes",
    )

    strict_validation = schema.get("strict_validation")
    if isinstance(strict_validation, dict):
        for key, expected in STRICT_VALIDATION.items():
            assert_equal(bool(strict_validation.get(key)), expected, f"strict_validation.{key}")

    compatibility_policy = schema.get("compatibility_policy")
    if isinstance(compatibility_policy, dict):
        for key, expected in COMPATIBILITY_POLICY.items():
            assert_equal(bool(compatibility_policy.get(key)), expected, f"compatibility_policy.{key}")

    provider_contracts = schema.get("provider_contracts", {})
    for provider, expected_contract in PROVIDER_CONTRACTS.items():
        actual_contract = provider_contracts.get(provider)
        if not isinstance(actual_contract, dict):
            raise RuntimeError(f"provider_contracts.{provider} is missing from canonical schema.")
        assert_equal(
            actual_contract.get("event_type"),
            expected_contract["event_type"],
            f"provider_contracts.{provider}.event_type",
        )
        assert_set_equal(
            actual_contract.get("endpoints", []),
            expected_contract["endpoints"],
            f"provider_contracts.{provider}.endpoints",
        )


def assert_v1_schema(schema: dict[str, Any]) -> None:
    assert_equal(schema.get("envelope_version"), EXPECTED_V1["envelope_version"], "envelope_version")
    assert_equal(schema.get("schema_version"), EXPECTED_V1["schema_version"], "schema_version")
    assert_set_equal(
        schema.get("optional_top_level_fields", []),
        EXPECTED_V1["optional_top_level_fields"],
        "optional_top_level_fields",
    )
    assert_common_schema(schema, v2=False)


def assert_v2_schema(schema: dict[str, Any]) -> None:
    assert_equal(schema.get("envelope_version"), EXPECTED_V2["envelope_version"], "envelope_version")
    assert_equal(schema.get("schema_version"), EXPECTED_V2["schema_version"], "schema_version")
    assert_set_equal(
        schema.get("optional_top_level_fields", []),
        EXPECTED_V2["optional_top_level_fields"],
        "optional_top_level_fields",
    )
    assert_set_equal(schema.get("span_kinds", []), EXPECTED_V2["span_kinds"], "span_kinds")
    assert_set_equal(schema.get("payload_types", []), EXPECTED_V2["payload_types"], "payload_types")
    assert_set_equal(schema.get("metrics_fields", []), EXPECTED_V2["metrics_fields"], "metrics_fields")
    assert_set_equal(schema.get("decision_fields", []), EXPECTED_V2["decision_fields"], "decision_fields")
    assert_common_schema(schema, v2=True)


def main() -> None:
    single_url = os.getenv("TOKVERA_CANONICAL_SCHEMA_URL")
    if single_url:
        schema = fetch_schema(single_url)
        if schema.get("schema_version") == EXPECTED_V2["schema_version"]:
            assert_v2_schema(schema)
            print(f"Canonical v2 envelope contract check passed.\nChecked URL: {single_url}")
            return
        assert_v1_schema(schema)
        print(f"Canonical v1 envelope contract check passed.\nChecked URL: {single_url}")
        return

    base_url = os.getenv("TOKVERA_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    v1_url = f"{base_url}/v1/schema/event-envelope-v1"

    assert_v1_schema(fetch_schema(v1_url))
    should_check_v2 = os.getenv("TOKVERA_CHECK_V2_CONTRACT") == "1"
    if not should_check_v2:
        print("Canonical v1 envelope contract check passed.")
        print(f"Checked URL: {v1_url}")
        print("Set TOKVERA_CHECK_V2_CONTRACT=1 to also validate v2 endpoint.")
        return

    v2_url = f"{base_url}/v1/schema/event-envelope-v2"
    assert_v2_schema(fetch_schema(v2_url))

    print("Canonical envelope contract checks passed for v1 and v2.")
    print(f"Checked URLs: {v1_url} | {v2_url}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
