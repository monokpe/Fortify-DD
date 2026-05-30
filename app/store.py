from dataclasses import dataclass
from threading import Lock
from uuid import UUID

from app.schemas import AssessmentResult, AssessmentStage, AssessmentStatus, WatchlistResponse


def _vendor_key(vendor: str) -> str:
    return " ".join(vendor.lower().strip().split())


@dataclass
class TaskRecord:
    result: AssessmentResult


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._records: dict[UUID, TaskRecord] = {}
        self._lock = Lock()

    def create(self, task_id: UUID) -> None:
        with self._lock:
            self._records[task_id] = TaskRecord(
                result=AssessmentResult(
                    status=AssessmentStatus.running,
                    stage=AssessmentStage.queued,
                )
            )

    def update_stage(self, task_id: UUID, stage: AssessmentStage) -> None:
        with self._lock:
            record = self._records.get(task_id)
            if not record:
                return
            record.result.stage = stage

    def complete(self, task_id: UUID, result: AssessmentResult) -> None:
        with self._lock:
            self._records[task_id] = TaskRecord(result=result)

    def fail(self, task_id: UUID, error: str) -> None:
        with self._lock:
            self._records[task_id] = TaskRecord(
                result=AssessmentResult(
                    status=AssessmentStatus.failed,
                    stage=AssessmentStage.failed,
                    error=error,
                )
            )

    def get(self, task_id: UUID) -> AssessmentResult | None:
        with self._lock:
            record = self._records.get(task_id)
            return record.result if record else None


task_store = InMemoryTaskStore()


class InMemoryWatchlistStore:
    def __init__(self) -> None:
        self._records: dict[str, WatchlistResponse] = {}
        self._lock = Lock()

    def upsert(
        self,
        vendor: str,
        schedule: str,
        webhook_url: str | None = None,
        domain: str | None = None,
    ) -> WatchlistResponse:
        with self._lock:
            existing = self._records.get(_vendor_key(vendor))
            stored_domain = domain if domain is not None else existing.domain if existing else None
            webhooks = list(existing.webhooks) if existing else []
            if webhook_url and webhook_url not in webhooks:
                webhooks.append(webhook_url)
            record = WatchlistResponse(
                vendor=vendor,
                domain=stored_domain,
                schedule=schedule,
                webhooks=webhooks,
            )
            self._records[_vendor_key(vendor)] = record
            return record

    def get(self, vendor: str) -> WatchlistResponse | None:
        with self._lock:
            return self._records.get(_vendor_key(vendor))

    def first(self) -> WatchlistResponse | None:
        with self._lock:
            return next(iter(self._records.values()), None)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


watchlist_store = InMemoryWatchlistStore()
