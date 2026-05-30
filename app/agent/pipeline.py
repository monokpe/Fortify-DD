from app.agent.state import AgentState
from app.clients.ai_ml import AIMLRouter
from app.clients.bright_data import BrightDataClient
from app.clients.cognee import CogneeMemoryClient
from app.clients.gemini import GeminiSynthesizer
from app.clients.speechmatics import SpeechmaticsClient
from app.clients.triggerware import TriggerWareClient
from collections.abc import Awaitable, Callable

from app.schemas import (
    AlertPayload,
    AssessmentOutput,
    AssessmentRequest,
    AssessmentStage,
    DeltaReport,
    RiskRating,
)

ProgressCallback = Callable[[AssessmentStage], Awaitable[None] | None]


class DueDiligencePipeline:
    def __init__(
        self,
        bright_data: BrightDataClient,
        synthesizer: GeminiSynthesizer,
        memory: CogneeMemoryClient,
        model_router: AIMLRouter,
        triggerware: TriggerWareClient,
        speechmatics: SpeechmaticsClient,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.bright_data = bright_data
        self.synthesizer = synthesizer
        self.memory = memory
        self.model_router = model_router
        self.triggerware = triggerware
        self.speechmatics = speechmatics
        self.progress_callback = progress_callback

    async def run(self, request: AssessmentRequest) -> AssessmentOutput:
        state: AgentState = {"request": request}
        await self._mark(AssessmentStage.memory)
        state = await self.memory_query_node(state)
        await self._mark(AssessmentStage.serp)
        state = await self.serp_node(state)
        await self._mark(AssessmentStage.triage)
        state = await self.triage_node(state)
        await self._mark(AssessmentStage.fetch)
        state = await self.fetch_node(state)
        await self._mark(AssessmentStage.regulatory)
        state = await self.sanctions_node(state)
        await self._mark(AssessmentStage.hiring)
        state = await self.hiring_node(state)
        await self._mark(AssessmentStage.synthesis)
        state = await self.synthesise_node(state)
        await self._mark(AssessmentStage.compare)
        state = await self.compare_node(state)
        await self._mark(AssessmentStage.store_memory)
        state = await self.store_memory_node(state)
        await self._mark(AssessmentStage.alert)
        state = await self.output_node(state)
        await self._mark(AssessmentStage.complete)
        return AssessmentOutput(
            risk_brief=state["risk_brief"],
            delta=state.get("delta"),
            alert=state.get("alert"),
            audio_url=state.get("audio_url"),
        )

    async def _mark(self, stage: AssessmentStage) -> None:
        if not self.progress_callback:
            return
        result = self.progress_callback(stage)
        if result is not None:
            await result

    async def memory_query_node(self, state: AgentState) -> AgentState:
        request = state["request"]
        state["previous_brief"] = await self.memory.get_latest_brief(request.company)
        return state

    async def serp_node(self, state: AgentState) -> AgentState:
        request = state["request"]
        state["search_results"] = await self.bright_data.search(request.company, request.domain)
        return state

    async def triage_node(self, state: AgentState) -> AgentState:
        state["ranked_sources"] = await self.model_router.triage_sources(
            state["search_results"],
            request=state["request"],
            limit=8,
        )
        return state

    async def fetch_node(self, state: AgentState) -> AgentState:
        ranked_sources = state.get("ranked_sources", state["search_results"][:8])
        state["search_results"] = ranked_sources
        state["pages"] = await self.bright_data.fetch_pages(ranked_sources)
        return state

    async def sanctions_node(self, state: AgentState) -> AgentState:
        request = state["request"]
        state["regulatory_findings"] = await self.bright_data.regulatory_checks(request.company)
        return state

    async def hiring_node(self, state: AgentState) -> AgentState:
        request = state["request"]
        state["hiring_signals"] = await self.bright_data.hiring_signals(request.company)
        return state

    async def synthesise_node(self, state: AgentState) -> AgentState:
        state["risk_brief"] = await self.synthesizer.synthesize(state)
        return state

    async def compare_node(self, state: AgentState) -> AgentState:
        brief = state["risk_brief"]
        previous = state.get("previous_brief")
        if not previous:
            state["delta"] = DeltaReport(
                vendor=brief.company,
                previous_rating=None,
                current_rating=brief.overall_rating,
                rating_changed=False,
                changed_dimensions=[],
                summary="No prior assessment found in memory; this brief establishes the baseline.",
            )
            return state

        changed_dimensions = [
            key
            for key, dimension in brief.dimensions.items()
            if key in previous.dimensions
            and (
                dimension.rating != previous.dimensions[key].rating
                or abs(dimension.score - previous.dimensions[key].score) >= 5
            )
        ]
        rating_changed = previous.overall_rating != brief.overall_rating
        change_word = "changed" if rating_changed or changed_dimensions else "unchanged"
        state["delta"] = DeltaReport(
            vendor=brief.company,
            previous_rating=previous.overall_rating,
            current_rating=brief.overall_rating,
            rating_changed=rating_changed,
            changed_dimensions=changed_dimensions,
            summary=(
                f"Risk is {change_word} versus the previous assessment. "
                f"Previous rating: {previous.overall_rating}; current rating: {brief.overall_rating}."
            ),
        )
        return state

    async def store_memory_node(self, state: AgentState) -> AgentState:
        await self.memory.store_brief(state["risk_brief"], state.get("delta"))
        return state

    async def output_node(self, state: AgentState) -> AgentState:
        brief = state["risk_brief"]
        delta = state.get("delta")
        if not delta:
            return state

        alert = AlertPayload(
            vendor=brief.company,
            prev_rating=delta.previous_rating,
            new_rating=brief.overall_rating,
            rating_changed=delta.rating_changed,
            dimensions_changed=delta.changed_dimensions,
            summary=delta.summary,
            recommended_action=brief.recommended_action,
        )
        if delta.rating_changed:
            await self.triggerware.fire_alert(alert)
        if brief.overall_rating == RiskRating.red:
            alert.audio_url = await self.speechmatics.create_alert_audio(alert)
            state["audio_url"] = alert.audio_url
        state["alert"] = alert
        return state
