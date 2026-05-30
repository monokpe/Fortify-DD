from uuid import uuid4

from app.schemas import AssessmentResult, AssessmentStage, AssessmentStatus, WatchlistResponse
from app.store import InMemoryTaskStore, InMemoryWatchlistStore


def test_task_store_lifecycle_updates_result_state() -> None:
    store = InMemoryTaskStore()
    task_id = uuid4()

    store.create(task_id)
    store.update_stage(task_id, AssessmentStage.fetch)

    running = store.get(task_id)
    assert running is not None
    assert running.status == AssessmentStatus.running
    assert running.stage == AssessmentStage.fetch

    completed = AssessmentResult(status=AssessmentStatus.complete, stage=AssessmentStage.complete)
    store.complete(task_id, completed)

    assert store.get(task_id) == completed


def test_task_store_fail_replaces_missing_or_existing_task_with_error() -> None:
    store = InMemoryTaskStore()
    task_id = uuid4()

    store.fail(task_id, "Network timeout")

    failed = store.get(task_id)
    assert failed is not None
    assert failed.status == AssessmentStatus.failed
    assert failed.stage == AssessmentStage.failed
    assert failed.error == "Network timeout"


def test_watchlist_store_normalizes_vendor_key_and_deduplicates_webhooks() -> None:
    store = InMemoryWatchlistStore()

    first = store.upsert(" Acme   Corp ", "daily", "https://hooks.example/one")
    second = store.upsert("acme corp", "weekly", "https://hooks.example/one")
    third = store.upsert("ACME CORP", "weekly", "https://hooks.example/two")

    assert first == WatchlistResponse(
        vendor=" Acme   Corp ",
        domain=None,
        schedule="daily",
        webhooks=["https://hooks.example/one"],
    )
    assert second.webhooks == ["https://hooks.example/one"]
    assert third.vendor == "ACME CORP"
    assert third.schedule == "weekly"
    assert third.webhooks == ["https://hooks.example/one", "https://hooks.example/two"]
    assert store.get("  acme    corp ") == third


def test_watchlist_store_preserves_domain_for_poll_fallback() -> None:
    store = InMemoryWatchlistStore()

    first = store.upsert("Acme Corp", "daily", domain="acme.example")
    second = store.upsert("acme corp", "weekly")

    assert first.domain == "acme.example"
    assert second.domain == "acme.example"
    assert store.first() == second
