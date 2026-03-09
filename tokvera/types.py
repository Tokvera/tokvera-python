from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Dict, Literal, Optional

EventStatus = Literal["success", "failure"]
SpanKind = Literal["model", "tool", "orchestrator", "retrieval", "guardrail"]
TracePayloadType = Literal["prompt_input", "tool_input", "tool_output", "model_output", "context", "other"]


@dataclass(frozen=True)
class TracePayloadBlock:
    payload_type: TracePayloadType
    content: str


@dataclass(frozen=True)
class TraceMetrics:
    prompt_tokens: Optional[float] = None
    completion_tokens: Optional[float] = None
    total_tokens: Optional[float] = None
    latency_ms: Optional[float] = None
    cost_usd: Optional[float] = None


@dataclass(frozen=True)
class TraceDecision:
    outcome: Optional[str] = None
    retry_reason: Optional[str] = None
    fallback_reason: Optional[str] = None
    routing_reason: Optional[str] = None
    route: Optional[str] = None


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
    outcome: Optional[str] = None
    retry_reason: Optional[str] = None
    fallback_reason: Optional[str] = None
    quality_label: Optional[str] = None
    feedback_score: Optional[float] = None
    capture_content: bool = False
    schema_version: Optional[str] = None
    span_kind: Optional[SpanKind] = None
    tool_name: Optional[str] = None
    payload_refs: Optional[list[str]] = None
    payload_blocks: Optional[list[TracePayloadBlock]] = None
    metrics: Optional[TraceMetrics] = None
    decision: Optional[TraceDecision] = None
    routing_reason: Optional[str] = None
    route: Optional[str] = None


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
    outcome: Optional[str]
    retry_reason: Optional[str]
    fallback_reason: Optional[str]
    quality_label: Optional[str]
    feedback_score: Optional[float]
    prompt_hash: Optional[str] = None
    response_hash: Optional[str] = None
    span_kind: Optional[SpanKind] = None
    tool_name: Optional[str] = None
    payload_refs: Optional[list[str]] = None
    payload_blocks: Optional[list[TracePayloadBlock]] = None
    metrics: Optional[TraceMetrics] = None
    decision: Optional[TraceDecision] = None
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
                "outcome": self.outcome,
                "retry_reason": self.retry_reason,
                "fallback_reason": self.fallback_reason,
                "quality_label": self.quality_label,
                "feedback_score": self.feedback_score,
            },
        }

        if any(
            value is not None
            for value in (
                self.outcome,
                self.retry_reason,
                self.fallback_reason,
                self.quality_label,
                self.feedback_score,
            )
        ):
            payload["evaluation"] = {
                "outcome": self.outcome,
                "retry_reason": self.retry_reason,
                "fallback_reason": self.fallback_reason,
                "quality_label": self.quality_label,
                "feedback_score": self.feedback_score,
            }

        if self.prompt_hash is not None:
            payload["prompt_hash"] = self.prompt_hash
        if self.response_hash is not None:
            payload["response_hash"] = self.response_hash
        if self.span_kind is not None:
            payload["span_kind"] = self.span_kind
        if self.tool_name is not None:
            payload["tool_name"] = self.tool_name
        if self.payload_refs:
            payload["payload_refs"] = list(self.payload_refs)
        if self.payload_blocks:
            payload["payload_blocks"] = [
                _compact_mapping(_to_mapping(item))
                for item in self.payload_blocks
                if _compact_mapping(_to_mapping(item))
            ]
        if self.metrics is not None:
            metrics = _compact_mapping(_to_mapping(self.metrics))
            if metrics:
                payload["metrics"] = metrics
        if self.decision is not None:
            decision = _compact_mapping(_to_mapping(self.decision))
            if decision:
                payload["decision"] = decision
        if self.error is not None:
            payload["error"] = {
                "type": self.error.type,
                "message": self.error.message,
            }

        return payload


def _to_mapping(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return {}


def _compact_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}
