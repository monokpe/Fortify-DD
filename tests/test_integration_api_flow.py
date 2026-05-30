from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


pytestmark = pytest.mark.integration


def _completed_assessment(client: TestClient, company: str, domain: str | None = None) -> dict:
    payload = {"company": company}
    if domain:
        payload["domain"] = domain

    created = client.post("/assess", json=payload)
    assert created.status_code == 202

    task_id = created.json()["task_id"]
    result = client.get(f"/assess/{task_id}")

    assert result.status_code == 200
    result_payload = result.json()
    assert result_payload["status"] == "complete"
    assert result_payload["stage"] == "complete"
    return result_payload


def test_assessment_flow_persists_history_and_reports_repeat_drift() -> None:
    client = TestClient(app)

    first = _completed_assessment(client, "Acme Corp", "https://acme.example/")
    second = _completed_assessment(client, "  Acme   Corp  ", "acme.example")

    assert first["risk_brief"]["company"] == "Acme Corp"
    assert first["delta"]["previous_rating"] is None
    assert first["delta"]["rating_changed"] is False
    assert first["delta"]["changed_dimensions"] == []
    assert len(first["risk_brief"]["sources"]) > 0

    assert second["risk_brief"]["company"] == "Acme Corp"
    assert second["delta"]["previous_rating"] == first["risk_brief"]["overall_rating"]
    assert second["delta"]["current_rating"] == second["risk_brief"]["overall_rating"]
    assert second["delta"]["rating_changed"] is False
    assert second["delta"]["changed_dimensions"] == ["financial_health"]

    history = client.get("/vendor/acme corp/history")
    assert history.status_code == 200
    history_payload = history.json()
    assert history_payload["vendor"] == "acme corp"
    assert len(history_payload["assessments"]) == 2
    assert len(history_payload["deltas"]) == 2
    assert history_payload["deltas"][1]["changed_dimensions"] == ["financial_health"]


def test_trigger_webhook_flow_uses_existing_memory_for_alert_diff() -> None:
    client = TestClient(app)

    baseline = _completed_assessment(client, "Globex Corp", "globex.example")
    alert = client.post(
        "/webhook/trigger",
        json={"company": "Globex Corp", "domain": "https://globex.example/"},
    )

    assert alert.status_code == 200
    alert_payload = alert.json()
    assert alert_payload["vendor"] == "Globex Corp"
    assert alert_payload["prev_rating"] == baseline["risk_brief"]["overall_rating"]
    assert alert_payload["new_rating"] == baseline["risk_brief"]["overall_rating"]
    assert alert_payload["rating_changed"] is False
    assert alert_payload["dimensions_changed"] == ["financial_health"]
    assert alert_payload["recommended_action"]
    assert alert_payload["audio_url"] is None

    history = client.get("/vendor/Globex Corp/history")
    assert history.status_code == 200
    assert len(history.json()["assessments"]) == 2


def test_watchlist_flow_upserts_existing_vendor_and_accumulates_webhooks() -> None:
    client = TestClient(app)

    first = client.post(
        "/watchlist",
        json={
            "company": "Umbrella Corp",
            "domain": "umbrella.example",
            "schedule": "daily",
            "webhook_url": "https://triggerware.example/primary",
        },
    )
    second = client.post(
        "/watchlist",
        json={
            "company": " umbrella   corp ",
            "schedule": "weekly",
            "webhook_url": "https://triggerware.example/escalation",
        },
    )

    assert first.status_code == 201
    assert first.json()["vendor"] == "Umbrella Corp"
    assert first.json()["schedule"] == "daily"

    assert second.status_code == 201
    assert second.json()["vendor"] == "umbrella corp"
    assert second.json()["schedule"] == "weekly"
    assert second.json()["webhooks"] == [
        "https://triggerware.example/primary",
        "https://triggerware.example/escalation",
    ]


def test_api_validation_and_missing_task_errors_are_exposed() -> None:
    client = TestClient(app)

    invalid_assessment = client.post("/assess", json={"company": "A"})
    invalid_watchlist = client.post(
        "/watchlist",
        json={"company": "Acme Corp", "schedule": "hourly"},
    )
    missing_task = client.get(f"/assess/{uuid4()}")

    assert invalid_assessment.status_code == 422
    assert invalid_watchlist.status_code == 422
    assert missing_task.status_code == 404
    assert missing_task.json()["detail"] == "Assessment task not found."
