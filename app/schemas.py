from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


class AssessmentStatus(StrEnum):
    running = "running"
    complete = "complete"
    failed = "failed"


class AssessmentStage(StrEnum):
    queued = "queued"
    memory = "memory"
    triage = "triage"
    serp = "serp"
    fetch = "fetch"
    regulatory = "regulatory"
    hiring = "hiring"
    synthesis = "synthesis"
    compare = "compare"
    store_memory = "store_memory"
    alert = "alert"
    complete = "complete"
    failed = "failed"


class RiskRating(StrEnum):
    green = "GREEN"
    amber = "AMBER"
    red = "RED"


class AssessmentRequest(BaseModel):
    company: str = Field(..., min_length=2, max_length=160)
    domain: str | None = Field(default=None, max_length=253)

    @field_validator("company")
    @classmethod
    def normalize_company(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value.strip().removeprefix("https://").removeprefix("http://").strip("/")


class AssessmentCreated(BaseModel):
    task_id: UUID
    status: Literal["running"]
    stage: AssessmentStage


class RiskDimension(BaseModel):
    rating: RiskRating
    score: int = Field(..., ge=0, le=100)
    summary: str = Field(..., min_length=1)


class Source(BaseModel):
    title: str
    url: HttpUrl | str
    source_type: str
    snippet: str | None = None


class RiskBrief(BaseModel):
    company: str
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    overall_rating: RiskRating
    overall_score: int = Field(..., ge=0, le=100)
    dimensions: dict[str, RiskDimension]
    sources: list[Source]
    summary: str | None = None
    recommended_action: str


class DeltaReport(BaseModel):
    vendor: str
    previous_rating: RiskRating | None = None
    current_rating: RiskRating
    rating_changed: bool = False
    changed_dimensions: list[str] = Field(default_factory=list)
    summary: str


class AlertPayload(BaseModel):
    vendor: str
    prev_rating: RiskRating | None = None
    new_rating: RiskRating
    rating_changed: bool
    dimensions_changed: list[str] = Field(default_factory=list)
    summary: str
    recommended_action: str
    audio_url: str | None = None


class AssessmentOutput(BaseModel):
    risk_brief: RiskBrief
    delta: DeltaReport | None = None
    alert: AlertPayload | None = None
    audio_url: str | None = None


class AssessmentResult(BaseModel):
    status: AssessmentStatus
    stage: AssessmentStage
    risk_brief: RiskBrief | None = None
    delta: DeltaReport | None = None
    alert: AlertPayload | None = None
    audio_url: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    mock_mode: bool


class VendorHistoryResponse(BaseModel):
    vendor: str
    assessments: list[RiskBrief] = Field(default_factory=list)
    deltas: list[DeltaReport] = Field(default_factory=list)


class WatchlistRequest(BaseModel):
    company: str = Field(..., min_length=2, max_length=160)
    domain: str | None = Field(default=None, max_length=253)
    schedule: str = Field(default="daily", pattern="^(daily|weekly)$")
    webhook_url: str | None = None

    @field_validator("company")
    @classmethod
    def normalize_company(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value.strip().removeprefix("https://").removeprefix("http://").strip("/")


class WatchlistResponse(BaseModel):
    vendor: str
    domain: str | None = None
    schedule: str
    webhooks: list[str] = Field(default_factory=list)


class TriggerRequest(BaseModel):
    company: str = Field(..., min_length=2, max_length=160)
    domain: str | None = Field(default=None, max_length=253)

    @field_validator("company")
    @classmethod
    def normalize_company(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value.strip().removeprefix("https://").removeprefix("http://").strip("/")


class TriggerPollRequest(BaseModel):
    company: str | None = Field(default=None, min_length=2, max_length=160)
    domain: str | None = Field(default=None, max_length=253)

    @field_validator("company")
    @classmethod
    def normalize_company(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.strip().split())

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value.strip().removeprefix("https://").removeprefix("http://").strip("/")
