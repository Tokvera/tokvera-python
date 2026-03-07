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
    "evaluation_fields": [
        "outcome",
        "retry_reason",
        "fallback_reason",
        "quality_label",
        "feedback_score",
    ],
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
    assert_set_equal(schema.get("status_values", []), EXPECTED["status_values"], "status_values")
    assert_set_equal(schema.get("usage_fields", []), EXPECTED["usage_fields"], "usage_fields")
    assert_set_equal(schema.get("evaluation_fields", []), EXPECTED["evaluation_fields"], "evaluation_fields")

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
