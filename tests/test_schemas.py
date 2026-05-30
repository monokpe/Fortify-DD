import pytest
from pydantic import ValidationError

from app.schemas import AssessmentRequest, RiskDimension, RiskRating, TriggerRequest, WatchlistRequest


def test_assessment_request_normalizes_company_and_domain() -> None:
    request = AssessmentRequest(
        company="  Acme    Corp  ",
        domain="https://www.acme.example/",
    )

    assert request.company == "Acme Corp"
    assert request.domain == "www.acme.example"


def test_trigger_request_normalizes_plain_http_domain() -> None:
    request = TriggerRequest(company="Globex", domain="http://globex.example/suppliers/")

    assert request.domain == "globex.example/suppliers"


def test_watchlist_request_rejects_unknown_schedule() -> None:
    with pytest.raises(ValidationError):
        WatchlistRequest(company="Initech", schedule="hourly")


def test_risk_dimension_validates_score_bounds_and_summary() -> None:
    valid = RiskDimension(rating=RiskRating.green, score=100, summary="No concern found.")

    assert valid.score == 100

    with pytest.raises(ValidationError):
        RiskDimension(rating=RiskRating.red, score=101, summary="Too high.")

    with pytest.raises(ValidationError):
        RiskDimension(rating=RiskRating.amber, score=50, summary="")
