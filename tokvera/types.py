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
    plan: Optional[str] = None
    environment: Optional[str] = None
    template_id: Optional[str] = None
    capture_content: bool = False


@dataclass(frozen=True)
class UsageMetrics:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class AnalyticsEvent:
    provider: str
    model: str
    feature: str
    tenant_id: str
    customer_id: Optional[str]
    plan: Optional[str]
    environment: Optional[str]
    template_id: Optional[str]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    status: EventStatus
    timestamp: str
    prompt_hash: Optional[str] = None
    response_hash: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "feature": self.feature,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "plan": self.plan,
            "environment": self.environment,
            "template_id": self.template_id,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "timestamp": self.timestamp,
        }

        if self.prompt_hash is not None:
            payload["prompt_hash"] = self.prompt_hash
        if self.response_hash is not None:
            payload["response_hash"] = self.response_hash

        return payload