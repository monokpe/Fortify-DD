import httpx
import pytest

from app.clients.ai_ml import AIMLRouter
from app.config import Settings
from app.schemas import AssessmentRequest, Source


def _sources() -> list[Source]:
    return [
        Source(
            title="Acme login",
            url="https://acme.example/login",
            source_type="company_site",
            snippet="Sign in.",
        ),
        Source(
            title="Acme SEC enforcement action",
            url="https://www.sec.gov/news/acme-enforcement",
            source_type="regulatory",
            snippet="SEC enforcement action involving Acme Corp.",
        ),
        Source(
            title="Acme funding update",
            url="https://news.example/acme-funding",
            source_type="news",
            snippet="Acme Corp funding update with public operating details.",
        ),
    ]


def test_parse_ranked_indices_accepts_json_strings_and_ignores_bad_payloads() -> None:
    router = AIMLRouter(Settings(mock_mode=False, aiml_api_key="token"))

    assert router._parse_ranked_indices(
        {"choices": [{"message": {"content": '{"ranked_indices": ["2", 1, "bad", null]}'}}]}
    ) == [2, 1]
    assert router._parse_ranked_indices({"choices": [{"message": {"content": "not json"}}]}) == []


@pytest.mark.asyncio
async def test_triage_sources_uses_model_order_then_fallback_for_remaining_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"ranked_indices": [2, 99, 2]}',
                        }
                    }
                ]
            },
        )

    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: async_client(transport=httpx.MockTransport(handler)),
    )
    router = AIMLRouter(
        Settings(
            mock_mode=False,
            aiml_api_key="token",
            aiml_base_url="https://api.aiml.example/v1/",
        )
    )

    ranked = await router.triage_sources(
        _sources(),
        request=AssessmentRequest(company="Acme Corp"),
        limit=2,
    )

    assert captured["url"] == "https://api.aiml.example/v1/chat/completions"
    assert captured["authorization"] == "Bearer token"
    assert [str(source.url) for source in ranked] == [
        "https://news.example/acme-funding",
        "https://www.sec.gov/news/acme-enforcement",
    ]
