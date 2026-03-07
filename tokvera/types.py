from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

EventStatus = Literal["success", "failure"]


@dataclass(frozen=True)
class TrackingContext:
    api_key: str
    feature: str
    tenant_id: str
    customer_id: Optional[str] = None
    attempt_type: Optional[str] = None
    plan: Optional[str] = None
    environment: Optional[str] = None
    template_id: Optional[str] = None
    trace_id: Optional[str] = None
    run_id: Optional[str] = None
    conversation_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    step_name: Optional[str] = None
    capture_content: bool = False


@dataclass(frozen=True)
class UsageMetrics:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class EventError:
    type: Optional[str] = None
    message: Optional[str] = None


@dataclass(frozen=True)
class AnalyticsEvent:
    schema_version: str
    event_type: str
    provider: str
    endpoint: str
    status: EventStatus
    timestamp: str
    latency_ms: int
    model: str
    usage: UsageMetrics
    feature: str
    tenant_id: str
    customer_id: Optional[str]
    attempt_type: Optional[str]
    plan: Optional[str]
    environment: Optional[str]
    template_id: Optional[str]
    trace_id: Optional[str]
    run_id: Optional[str]
    conversation_id: Optional[str]
    span_id: Optional[str]
    parent_span_id: Optional[str]
    step_name: Optional[str]
    prompt_hash: Optional[str] = None
    response_hash: Optional[str] = None
    error: Optional[EventError] = None

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "status": self.status,
            "timestamp": self.timestamp,
            "latency_ms": self.latency_ms,
            "model": self.model,
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
            },
            "tags": {
                "feature": self.feature,
                "tenant_id": self.tenant_id,
                "customer_id": self.customer_id,
                "attempt_type": self.attempt_type,
                "plan": self.plan,
                "environment": self.environment,
                "template_id": self.template_id,
                "trace_id": self.trace_id,
                "run_id": self.run_id,
                "conversation_id": self.conversation_id,
                "span_id": self.span_id,
                "parent_span_id": self.parent_span_id,
                "step_name": self.step_name,
            },
        }

        if self.prompt_hash is not None:
            payload["prompt_hash"] = self.prompt_hash
        if self.response_hash is not None:
            payload["response_hash"] = self.response_hash
        if self.error is not None:
            payload["error"] = {
                "type": self.error.type,
                "message": self.error.message,
            }

        return payload
