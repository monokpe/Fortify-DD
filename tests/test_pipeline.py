from collections.abc import Awaitable, Callable

import pytest

from app.agent.pipeline import DueDiligencePipeline
from app.schemas import (
    AlertPayload,
    AssessmentRequest,
    AssessmentStage,
    DeltaReport,
    RiskBrief,
    RiskDimension,
    RiskRating,
    Source,
)


def make_brief(
    *,
    company: str = "Acme Corp",
    rating: RiskRating = RiskRating.amber,
    financial_score: int = 61,
    financial_rating: RiskRating = RiskRating.amber,
) -> RiskBrief:
    return RiskBrief(
        company=company,
        overall_rating=rating,
        overall_score=65,
        dimensions={
            "reputational": RiskDimension(
                rating=RiskRating.amber,
                score=68,
                summary="Some reputational uncertainty.",
            ),
            "financial_health": RiskDimension(
                rating=financial_rating,
                score=financial_score,
                summary="Financial public signals need review.",
            ),
            "regulatory_legal": RiskDimension(
                rating=RiskRating.green,
                score=82,
                summary="No exact regulatory match.",
            ),
            "operational_stability": RiskDimension(
                rating=RiskRating.green,
                score=74,
                summary="Operating normally.",
            ),
            "supply_chain": RiskDimension(
                rating=RiskRating.amber,
                score=58,
                summary="Third-party visibility is incomplete.",
            ),
        },
        sources=[
            Source(
                title="Fixture source",
                url="https://example.com/acme",
                source_type="fixture",
            )
        ],
        summary="Fixture brief.",
        recommended_action="Proceed with review.",
    )


class StubBrightData:
    async def search(self, company: str, domain: str | None = None) -> list[Source]:
        return [Source(title=f"{company} news", url="https://example.com/news", source_type="news")]

    async def fetch_pages(self, sources: list[Source]) -> list[dict[str, str]]:
        return [{"title": source.title, "url": str(source.url), "content": "content"} for source in sources]

    async def regulatory_checks(self, company: str) -> list[dict[str, str]]:
        return [{"source": "OFAC", "status": "no_match", "summary": "No match."}]

    async def hiring_signals(self, company: str) -> list[dict[str, str]]:
        return [{"source": "LinkedIn", "summary": "Moderate hiring."}]


class StubSynthesizer:
    def __init__(self, brief: RiskBrief) -> None:
        self.brief = brief

    async def synthesize(self, state: dict) -> RiskBrief:
        return self.brief


class StubMemory:
    def __init__(self, previous: RiskBrief | None = None) -> None:
        self.previous = previous
        self.stored: list[tuple[RiskBrief, DeltaReport | None]] = []

    async def get_latest_brief(self, vendor: str) -> RiskBrief | None:
        return self.previous

    async def store_brief(self, brief: RiskBrief, delta: DeltaReport | None = None) -> None:
        self.stored.append((brief, delta))


class StubRouter:
    async def triage_sources(
        self,
        sources: list[Source],
        request: AssessmentRequest,
        limit: int = 8,
    ) -> list[Source]:
        return sources[:limit]


class StubTriggerWare:
    def __init__(self) -> None:
        self.alerts: list[AlertPayload] = []

    async def fire_alert(self, alert: AlertPayload) -> None:
        self.alerts.append(alert)


class StubSpeechmatics:
    async def create_alert_audio(self, alert: AlertPayload) -> str:
        return f"https://audio.example/{alert.vendor.replace(' ', '-')}.mp3"


def make_pipeline(
    *,
    brief: RiskBrief,
    previous: RiskBrief | None = None,
    progress_callback: Callable[[AssessmentStage], Awaitable[None] | None] | None = None,
) -> tuple[DueDiligencePipeline, StubMemory, StubTriggerWare]:
    memory = StubMemory(previous=previous)
    triggerware = StubTriggerWare()
    pipeline = DueDiligencePipeline(
        bright_data=StubBrightData(),
        synthesizer=StubSynthesizer(brief),
        memory=memory,
        model_router=StubRouter(),
        triggerware=triggerware,
        speechmatics=StubSpeechmatics(),
        progress_callback=progress_callback,
    )
    return pipeline, memory, triggerware


@pytest.mark.asyncio
async def test_compare_node_creates_baseline_delta_without_previous_brief() -> None:
    brief = make_brief()
    pipeline, _, _ = make_pipeline(brief=brief)

    state = await pipeline.compare_node({"request": AssessmentRequest(company="Acme Corp"), "risk_brief": brief})

    assert state["delta"].previous_rating is None
    assert state["delta"].current_rating == RiskRating.amber
    assert state["delta"].rating_changed is False
    assert state["delta"].changed_dimensions == []


@pytest.mark.asyncio
async def test_compare_node_detects_rating_and_dimension_drift() -> None:
    previous = make_brief(rating=RiskRating.green, financial_score=75, financial_rating=RiskRating.green)
    current = make_brief(rating=RiskRating.amber, financial_score=66, financial_rating=RiskRating.amber)
    pipeline, _, _ = make_pipeline(brief=current, previous=previous)

    state = await pipeline.compare_node(
        {
            "request": AssessmentRequest(company="Acme Corp"),
            "risk_brief": current,
            "previous_brief": previous,
        }
    )

    assert state["delta"].previous_rating == RiskRating.green
    assert state["delta"].current_rating == RiskRating.amber
    assert state["delta"].rating_changed is True
    assert state["delta"].changed_dimensions == ["financial_health"]


@pytest.mark.asyncio
async def test_output_node_fires_triggerware_only_when_rating_changed() -> None:
    brief = make_brief(rating=RiskRating.amber)
    pipeline, _, triggerware = make_pipeline(brief=brief)

    unchanged_state = await pipeline.output_node(
        {
            "risk_brief": brief,
            "delta": DeltaReport(
                vendor="Acme Corp",
                previous_rating=RiskRating.amber,
                current_rating=RiskRating.amber,
                rating_changed=False,
                summary="Unchanged.",
            ),
        }
    )
    changed_state = await pipeline.output_node(
        {
            "risk_brief": brief,
            "delta": DeltaReport(
                vendor="Acme Corp",
                previous_rating=RiskRating.green,
                current_rating=RiskRating.amber,
                rating_changed=True,
                changed_dimensions=["financial_health"],
                summary="Changed.",
            ),
        }
    )

    assert unchanged_state["alert"].rating_changed is False
    assert changed_state["alert"].rating_changed is True
    assert changed_state["alert"].dimensions_changed == ["financial_health"]
    assert len(triggerware.alerts) == 1


@pytest.mark.asyncio
async def test_run_marks_stages_stores_memory_and_adds_audio_for_red_alert() -> None:
    stages: list[AssessmentStage] = []
    previous = make_brief(rating=RiskRating.amber)
    current = make_brief(rating=RiskRating.red)
    pipeline, memory, triggerware = make_pipeline(
        brief=current,
        previous=previous,
        progress_callback=stages.append,
    )

    output = await pipeline.run(AssessmentRequest(company="Acme Corp", domain="acme.example"))

    assert stages == [
        AssessmentStage.memory,
        AssessmentStage.serp,
        AssessmentStage.triage,
        AssessmentStage.fetch,
        AssessmentStage.regulatory,
        AssessmentStage.hiring,
        AssessmentStage.synthesis,
        AssessmentStage.compare,
        AssessmentStage.store_memory,
        AssessmentStage.alert,
        AssessmentStage.complete,
    ]
    assert output.risk_brief == current
    assert output.alert is not None
    assert output.alert.rating_changed is True
    assert output.audio_url == "https://audio.example/Acme-Corp.mp3"
    assert output.alert.audio_url == output.audio_url
    assert memory.stored == [(current, output.delta)]
    assert triggerware.alerts == [output.alert]
