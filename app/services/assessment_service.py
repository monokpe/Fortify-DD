from uuid import UUID, uuid4

from app.agent.pipeline import DueDiligencePipeline
from app.clients.ai_ml import AIMLRouter
from app.clients.bright_data import BrightDataClient
from app.clients.cognee import CogneeMemoryClient
from app.clients.gemini import GeminiSynthesizer
from app.clients.speechmatics import SpeechmaticsClient
from app.clients.triggerware import TriggerWareClient
from app.config import get_settings
from app.agent.pipeline import ProgressCallback
from app.schemas import AssessmentOutput, AssessmentRequest, AssessmentResult, AssessmentStage, AssessmentStatus
from app.store import InMemoryTaskStore, task_store


class AssessmentService:
    def __init__(self, store: InMemoryTaskStore = task_store) -> None:
        self.store = store

    def create_task(self) -> UUID:
        task_id = uuid4()
        self.store.create(task_id)
        return task_id

    async def run_assessment(self, task_id: UUID, request: AssessmentRequest) -> None:
        try:
            output = await self.run_inline(
                request,
                progress_callback=lambda stage: self.store.update_stage(task_id, stage),
            )
            self.store.complete(
                task_id,
                AssessmentResult(
                    status=AssessmentStatus.complete,
                    stage=AssessmentStage.complete,
                    risk_brief=output.risk_brief,
                    delta=output.delta,
                    alert=output.alert,
                    audio_url=output.audio_url,
                ),
            )
        except Exception as exc:
            self.store.fail(task_id, str(exc))

    async def run_inline(
        self,
        request: AssessmentRequest,
        progress_callback: ProgressCallback | None = None,
    ) -> AssessmentOutput:
        settings = get_settings()
        pipeline = DueDiligencePipeline(
            bright_data=BrightDataClient(settings),
            synthesizer=GeminiSynthesizer(settings),
            memory=CogneeMemoryClient(settings),
            model_router=AIMLRouter(settings),
            triggerware=TriggerWareClient(settings),
            speechmatics=SpeechmaticsClient(settings),
            progress_callback=progress_callback,
        )
        return await pipeline.run(request)

    def get_result(self, task_id: UUID) -> AssessmentResult | None:
        return self.store.get(task_id)


assessment_service = AssessmentService()
