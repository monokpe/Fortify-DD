from typing import TypedDict

from app.schemas import AlertPayload, AssessmentRequest, DeltaReport, RiskBrief, Source


class PageContent(TypedDict):
    title: str
    url: str
    content: str
    source_type: str


class RegulatoryFinding(TypedDict):
    source: str
    status: str
    summary: str
    url: str


class HiringSignal(TypedDict):
    source: str
    summary: str
    sentiment: str
    url: str


class AgentState(TypedDict, total=False):
    request: AssessmentRequest
    previous_brief: RiskBrief | None
    search_results: list[Source]
    ranked_sources: list[Source]
    pages: list[PageContent]
    regulatory_findings: list[RegulatoryFinding]
    hiring_signals: list[HiringSignal]
    risk_brief: RiskBrief
    delta: DeltaReport | None
    alert: AlertPayload | None
    audio_url: str | None
