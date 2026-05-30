from uuid import UUID

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException

from app.config import get_settings
from app.schemas import (
    AlertPayload,
    AssessmentCreated,
    AssessmentRequest,
    AssessmentResult,
    AssessmentStage,
    HealthResponse,
    TriggerPollRequest,
    TriggerRequest,
    VendorHistoryResponse,
    WatchlistRequest,
    WatchlistResponse,
)
from app.services.assessment_service import assessment_service
from app.clients.cognee import CogneeMemoryClient
from app.store import watchlist_store

app = FastAPI(
    title="Fortify DD",
    description="Bulletproof due diligence in seconds.",
    version="0.1.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "Fortify DD",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", mock_mode=settings.mock_mode)


@app.post("/assess", response_model=AssessmentCreated, status_code=202)
async def create_assessment(
    payload: AssessmentRequest,
    background_tasks: BackgroundTasks,
) -> AssessmentCreated:
    task_id = assessment_service.create_task()
    background_tasks.add_task(assessment_service.run_assessment, task_id, payload)
    return AssessmentCreated(task_id=task_id, status="running", stage=AssessmentStage.queued)


@app.get("/assess/{task_id}", response_model=AssessmentResult)
async def get_assessment(task_id: UUID) -> AssessmentResult:
    result = assessment_service.get_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment task not found.")
    return result


@app.get("/vendor/{name}/history", response_model=VendorHistoryResponse)
async def get_vendor_history(name: str) -> VendorHistoryResponse:
    memory = CogneeMemoryClient(get_settings())
    history = await memory.get_history(name)
    return VendorHistoryResponse(
        vendor=name,
        assessments=history.assessments,
        deltas=history.deltas,
    )


@app.post("/watchlist", response_model=WatchlistResponse, status_code=201)
async def create_watchlist_entry(payload: WatchlistRequest) -> WatchlistResponse:
    webhook = payload.webhook_url or get_settings().triggerware_webhook_url
    return watchlist_store.upsert(payload.company, payload.schedule, webhook, payload.domain)


@app.post("/webhook/trigger", response_model=AlertPayload)
async def trigger_watchlist_assessment(payload: TriggerRequest) -> AlertPayload:
    return await _run_trigger_assessment(payload.company, payload.domain)


@app.get("/triggerware/poll", response_model=AlertPayload)
async def poll_triggerware_fallback(
    company: str | None = None,
    domain: str | None = None,
) -> AlertPayload:
    payload = TriggerPollRequest(company=company, domain=domain)
    company, domain = _resolve_poll_target(payload)
    return await _run_trigger_assessment(company, domain)


@app.post("/triggerware/poll", response_model=AlertPayload)
async def post_triggerware_poll_fallback(
    payload: TriggerPollRequest | None = Body(default=None),
) -> AlertPayload:
    company, domain = _resolve_poll_target(payload or TriggerPollRequest())
    return await _run_trigger_assessment(company, domain)


def _resolve_poll_target(payload: TriggerPollRequest) -> tuple[str, str | None]:
    if payload.company:
        return payload.company, payload.domain

    entry = watchlist_store.first()
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="No watchlist entry available for TriggerWare polling.",
        )
    return entry.vendor, entry.domain


async def _run_trigger_assessment(company: str, domain: str | None) -> AlertPayload:
    output = await assessment_service.run_inline(
        AssessmentRequest(company=company, domain=domain)
    )
    if output.alert is None:
        raise HTTPException(status_code=500, detail="Assessment completed without alert payload.")
    return output.alert
