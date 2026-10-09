"""Versioned input contracts for the local Tempo agent."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FocusEvent(StrictModel):
    schema_version: Literal["1.0"]
    event_id: UUID
    user_id: Literal["demo-user"]
    observed_at: datetime
    source: Literal["simulator", "muse2", "replay"]
    state: Literal["focused", "focus_dip", "unknown"]
    focus_score: float | None = Field(ge=0, le=1)
    signal_quality: Literal["good", "poor", "disconnected"]
    sustained_for_ms: int = Field(ge=0)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at requires a timezone")
        return value


class Mandate(StrictModel):
    schema_version: Literal["1.0"]
    user_id: Literal["demo-user"]
    enabled: bool
    currency: Literal["SGD"]
    max_order_minor: int = Field(ge=1)
    daily_budget_minor: int = Field(ge=1)
    max_orders_per_day: int = Field(ge=1)
    cooldown_seconds: int = Field(ge=0)
    allowed_merchant_domains: list[str] = Field(min_length=1)
    preferred_product_id: str | None = None
    approval_mode: Literal["each_order"] = "each_order"
    cancel_window_seconds: int = Field(default=15, ge=0)


class Action(StrictModel):
    schema_version: Literal["1.0"]
    user_id: Literal["demo-user"]
    action_id: UUID
    action: Literal["approve", "cancel", "pause", "resume"]
    order_id: UUID | None = None
