import pytest

from app.schemas import AssessmentRequest, Source
from app.services.source_ranker import SourceRanker


def test_rank_prioritizes_relevant_risk_sources() -> None:
    request = AssessmentRequest(company="Acme Corp", domain="acme.com")
    sources = [
        Source(
            title="Acme Corp privacy policy",
            url="https://acme.com/privacy",
            source_type="company_site",
            snippet="Privacy policy and cookie notice.",
        ),
        Source(
            title="Acme Corp enforcement action",
            url="https://www.sec.gov/news/acme-enforcement",
            source_type="regulatory",
            snippet="SEC investigation and enforcement action involving Acme Corp.",
        ),
        Source(
            title="Acme Corp sign in",
            url="https://acme.com/login",
            source_type="company_site",
            snippet="Login to your account.",
        ),
        Source(
            title="Acme Corp jobs",
            url="https://www.linkedin.com/jobs/acme-corp",
            source_type="hiring",
            snippet="Open jobs at Acme Corp.",
        ),
    ]

    ranked = SourceRanker().rank(sources, request)

    assert ranked[0].url == "https://www.sec.gov/news/acme-enforcement"
    assert ranked[-1].url == "https://acme.com/login"


def test_rank_deduplicates_normalized_urls_and_applies_limit() -> None:
    request = AssessmentRequest(company="Acme Corp")
    sources = [
        Source(
            title="First Acme lawsuit story",
            url="https://example.com/acme-lawsuit/",
            source_type="news",
            snippet="Acme Corp lawsuit coverage.",
        ),
        Source(
            title="Duplicate Acme lawsuit story",
            url="https://www.example.com/acme-lawsuit",
            source_type="news",
            snippet="Duplicate Acme Corp lawsuit coverage.",
        ),
        Source(
            title="Acme funding",
            url="https://example.com/acme-funding",
            source_type="news",
            snippet="Acme Corp funding update.",
        ),
    ]

    ranked = SourceRanker().rank(sources, request, limit=2)

    assert len(ranked) == 2
    assert [str(source.url) for source in ranked] == [
        "https://example.com/acme-lawsuit/",
        "https://example.com/acme-funding",
    ]


def test_score_boosts_known_risk_domains() -> None:
    request = AssessmentRequest(company="Acme Corp")
    ranker = SourceRanker()
    sec_source = Source(
        title="Acme Corp filing",
        url="https://www.sec.gov/news/acme-filing",
        source_type="serp",
        snippet="Acme Corp public filing.",
    )
    generic_source = Source(
        title="Acme Corp filing",
        url="https://example.com/news/acme-filing",
        source_type="serp",
        snippet="Acme Corp public filing.",
    )

    assert ranker.score(sec_source, request) > ranker.score(generic_source, request)


def test_score_boosts_pdf_sources() -> None:
    request = AssessmentRequest(company="Acme Corp")
    ranker = SourceRanker()
    html_source = Source(
        title="Acme Corp risk report",
        url="https://example.com/acme-risk-report",
        source_type="news",
        snippet="Acme Corp risk report.",
    )
    pdf_source = Source(
        title="Acme Corp risk report",
        url="https://example.com/acme-risk-report.pdf",
        source_type="news",
        snippet="Acme Corp risk report.",
    )

    assert ranker.score(pdf_source, request) == ranker.score(html_source, request) + 3


@pytest.mark.parametrize(
    ("source", "assessment_request"),
    [
        (
            Source(
                title="Acme Corp lawsuit update",
                url="https://example.com/story",
                source_type="news",
                snippet="Legal coverage.",
            ),
            AssessmentRequest(company="Acme Corp"),
        ),
        (
            Source(
                title="Vendor lawsuit update",
                url="https://risk.acme.com/story",
                source_type="news",
                snippet="Legal coverage.",
            ),
            AssessmentRequest(company="Acme Corp", domain="acme.com"),
        ),
    ],
)
def test_score_boosts_company_and_domain_matches(
    source: Source,
    assessment_request: AssessmentRequest,
) -> None:
    ranker = SourceRanker()
    neutral_source = Source(
        title="Vendor lawsuit update",
        url="https://example.com/story",
        source_type="news",
        snippet="Legal coverage.",
    )

    assert ranker.score(source, assessment_request) > ranker.score(
        neutral_source,
        assessment_request,
    )


def test_score_penalizes_low_value_pages() -> None:
    request = AssessmentRequest(company="Acme Corp", domain="acme.com")
    ranker = SourceRanker()
    low_value_source = Source(
        title="Acme Corp privacy policy and cookie notice",
        url="https://acme.com/login",
        source_type="company_site",
        snippet="Sign in to register for account access.",
    )
    useful_source = Source(
        title="Acme Corp supplier update",
        url="https://acme.com/suppliers",
        source_type="company_site",
        snippet="Supplier operating update for Acme Corp.",
    )

    assert ranker.score(low_value_source, request) < ranker.score(useful_source, request)
