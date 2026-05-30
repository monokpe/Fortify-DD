from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_assessment_runs_fixture_pipeline() -> None:
    client = TestClient(app)

    created = client.post("/assess", json={"company": "Acme Corp", "domain": "acme.com"})

    assert created.status_code == 202
    created_payload = created.json()
    assert created_payload["stage"] == "queued"
    task_id = created_payload["task_id"]

    result = client.get(f"/assess/{task_id}")

    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] in {"running", "complete"}
    assert payload["stage"] in {
        "queued",
        "memory",
        "serp",
        "triage",
        "fetch",
        "regulatory",
        "hiring",
        "synthesis",
        "compare",
        "store_memory",
        "alert",
        "complete",
    }
    if payload["status"] == "complete":
        assert payload["risk_brief"]["company"] == "Acme Corp"
        assert payload["risk_brief"]["overall_rating"] in {"GREEN", "AMBER", "RED"}
        assert payload["delta"]["current_rating"] in {"GREEN", "AMBER", "RED"}


def test_vendor_history_and_trigger_webhook_use_memory() -> None:
    client = TestClient(app)

    alert = client.post(
        "/webhook/trigger",
        json={"company": "Globex Corp", "domain": "globex.com"},
    )

    assert alert.status_code == 200
    alert_payload = alert.json()
    assert alert_payload["vendor"] == "Globex Corp"
    assert alert_payload["new_rating"] in {"GREEN", "AMBER", "RED"}
    assert alert_payload["rating_changed"] is False

    history = client.get("/vendor/Globex Corp/history")

    assert history.status_code == 200
    history_payload = history.json()
    assert history_payload["vendor"] == "Globex Corp"
    assert len(history_payload["assessments"]) == 1
    assert len(history_payload["deltas"]) == 1


def test_watchlist_endpoint_records_vendor() -> None:
    client = TestClient(app)

    response = client.post(
        "/watchlist",
        json={
            "company": "Initech",
            "domain": "initech.example",
            "schedule": "weekly",
            "webhook_url": "https://triggerware.example/webhook",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["vendor"] == "Initech"
    assert payload["domain"] == "initech.example"
    assert payload["schedule"] == "weekly"
    assert payload["webhooks"] == ["https://triggerware.example/webhook"]


def test_triggerware_poll_fallback_uses_watchlist_when_payload_is_empty() -> None:
    client = TestClient(app)

    watchlist = client.post(
        "/watchlist",
        json={
            "company": "Soylent Corp",
            "domain": "https://soylent.example/",
            "schedule": "daily",
        },
    )
    alert = client.post("/triggerware/poll", json={})

    assert watchlist.status_code == 201
    assert alert.status_code == 200
    alert_payload = alert.json()
    assert alert_payload["vendor"] == "Soylent Corp"
    assert alert_payload["new_rating"] in {"GREEN", "AMBER", "RED"}
    assert alert_payload["rating_changed"] is False


def test_triggerware_poll_accepts_explicit_get_target() -> None:
    client = TestClient(app)

    alert = client.get(
        "/triggerware/poll",
        params={"company": "Hooli", "domain": "http://hooli.example/"},
    )

    assert alert.status_code == 200
    assert alert.json()["vendor"] == "Hooli"


def test_triggerware_poll_requires_target_or_watchlist() -> None:
    client = TestClient(app)

    alert = client.post("/triggerware/poll", json={})

    assert alert.status_code == 404
    assert alert.json()["detail"] == "No watchlist entry available for TriggerWare polling."
