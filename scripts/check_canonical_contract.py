from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_CONTRACT_URL = "https://api.tokvera.org/v1/schema/event-envelope-v1"

EXPECTED = {
    "envelope_version": "v1",
    "schema_version": "2026-02-16",
    "required_top_level_fields": [
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
    ],
    "optional_top_level_fields": ["prompt_hash", "response_hash", "error", "evaluation"],
    "strict_validation": {
        "allow_unknown_top_level_fields": False,
        "allow_unknown_usage_fields": False,
        "allow_unknown_tag_fields": False,
        "allow_unknown_evaluation_fields": False,
        "allow_unknown_error_fields": False,
    },
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
    "status_values": ["success", "failure"],
    "provider_contracts": {
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
    },
    "usage_fields": ["prompt_tokens", "completion_tokens", "total_tokens"],
    "error_fields": ["type", "message"],
    "allowed_tag_fields": [
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
    ],
    "evaluation_fields": [
        "outcome",
        "retry_reason",
        "fallback_reason",
        "quality_label",
        "feedback_score",
    ],
    "compatibility_policy": {
        "additive_optional_fields": True,
        "required_fields_require_schema_bump": True,
        "semantic_changes_require_schema_bump": True,
        "deprecations_require_staged_rollout": True,
    },
}


def as_sorted_set(values: list[str]) -> list[str]:
    return sorted(set(values))


def assert_equal(actual: str, expected: str, label: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{label} mismatch. expected={expected} actual={actual}")


def assert_set_equal(actual: list[str], expected: list[str], label: str) -> None:
    actual_sorted = as_sorted_set(actual)
    expected_sorted = as_sorted_set(expected)
    if actual_sorted != expected_sorted:
        raise RuntimeError(
            f"{label} mismatch.\nexpected={json.dumps(expected_sorted)}\nactual={json.dumps(actual_sorted)}"
        )


def main() -> None:
    url = os.getenv("TOKVERA_CANONICAL_SCHEMA_URL", DEFAULT_CONTRACT_URL)

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
        raise RuntimeError(f"Canonical contract request failed: {exc}") from exc

    if not payload.get("ok") or not isinstance(payload.get("schema"), dict):
        raise RuntimeError("Canonical contract response payload format is invalid.")

    schema = payload["schema"]
    assert_equal(schema.get("envelope_version"), EXPECTED["envelope_version"], "envelope_version")
    assert_equal(schema.get("schema_version"), EXPECTED["schema_version"], "schema_version")
    assert_set_equal(schema.get("required_top_level_fields", []), EXPECTED["required_top_level_fields"], "required_top_level_fields")
    assert_set_equal(schema.get("optional_top_level_fields", []), EXPECTED["optional_top_level_fields"], "optional_top_level_fields")
    assert_set_equal(schema.get("status_values", []), EXPECTED["status_values"], "status_values")
    assert_set_equal(schema.get("usage_fields", []), EXPECTED["usage_fields"], "usage_fields")
    assert_set_equal(schema.get("allowed_tag_fields", []), EXPECTED["allowed_tag_fields"], "allowed_tag_fields")
    assert_set_equal(schema.get("evaluation_fields", []), EXPECTED["evaluation_fields"], "evaluation_fields")
    compatibility_policy = schema.get("compatibility_policy", {})
    assert_equal(
        bool(compatibility_policy.get("additive_optional_fields")),
        EXPECTED["compatibility_policy"]["additive_optional_fields"],
        "compatibility_policy.additive_optional_fields",
    )
    assert_equal(
        bool(compatibility_policy.get("required_fields_require_schema_bump")),
        EXPECTED["compatibility_policy"]["required_fields_require_schema_bump"],
        "compatibility_policy.required_fields_require_schema_bump",
    )
    assert_equal(
        bool(compatibility_policy.get("semantic_changes_require_schema_bump")),
        EXPECTED["compatibility_policy"]["semantic_changes_require_schema_bump"],
        "compatibility_policy.semantic_changes_require_schema_bump",
    )
    assert_equal(
        bool(compatibility_policy.get("deprecations_require_staged_rollout")),
        EXPECTED["compatibility_policy"]["deprecations_require_staged_rollout"],
        "compatibility_policy.deprecations_require_staged_rollout",
    )

    strict_validation = schema.get("strict_validation")
    if isinstance(strict_validation, dict):
        assert_equal(
            bool(strict_validation.get("allow_unknown_top_level_fields")),
            EXPECTED["strict_validation"]["allow_unknown_top_level_fields"],
            "strict_validation.allow_unknown_top_level_fields",
        )
        assert_equal(
            bool(strict_validation.get("allow_unknown_usage_fields")),
            EXPECTED["strict_validation"]["allow_unknown_usage_fields"],
            "strict_validation.allow_unknown_usage_fields",
        )
        assert_equal(
            bool(strict_validation.get("allow_unknown_tag_fields")),
            EXPECTED["strict_validation"]["allow_unknown_tag_fields"],
            "strict_validation.allow_unknown_tag_fields",
        )
        assert_equal(
            bool(strict_validation.get("allow_unknown_evaluation_fields")),
            EXPECTED["strict_validation"]["allow_unknown_evaluation_fields"],
            "strict_validation.allow_unknown_evaluation_fields",
        )
        assert_equal(
            bool(strict_validation.get("allow_unknown_error_fields")),
            EXPECTED["strict_validation"]["allow_unknown_error_fields"],
            "strict_validation.allow_unknown_error_fields",
        )

    validation_error_codes = schema.get("validation_error_codes")
    if isinstance(validation_error_codes, list):
        assert_set_equal(
            validation_error_codes,
            EXPECTED["validation_error_codes"],
            "validation_error_codes",
        )

    error_fields = schema.get("error_fields")
    if isinstance(error_fields, list):
        assert_set_equal(error_fields, EXPECTED["error_fields"], "error_fields")

    provider_contracts = schema.get("provider_contracts", {})
    for provider, expected_contract in EXPECTED["provider_contracts"].items():
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

    print("Canonical envelope contract check passed.")
    print(f"Checked URL: {url}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
