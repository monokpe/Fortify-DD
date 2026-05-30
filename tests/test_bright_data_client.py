import httpx
import pytest

from app.clients.bright_data import BrightDataClient
from app.config import Settings
from app.schemas import Source


@pytest.mark.asyncio
async def test_serp_uses_bright_data_request_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "url": str(request.url),
                "headers": request.headers,
                "json": request.read().decode(),
            }
        )
        return httpx.Response(
            200,
            json={
                "organic": [
                    {
                        "title": "Acme result",
                        "link": "https://example.com/acme",
                        "snippet": "A useful source.",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=transport))
    client = BrightDataClient(
        Settings(
            mock_mode=False,
            bright_data_api_key="token",
            bright_data_request_endpoint="https://api.brightdata.com/request",
            bright_data_serp_zone="serp-zone",
            bright_data_web_unlocker_zone="unlocker-zone",
        )
    )

    results = await client.search("Acme Corp")

    assert results[0].url == "https://example.com/acme"
    assert captured[0]["url"] == "https://api.brightdata.com/request"
    assert "Bearer token" in captured[0]["headers"]["authorization"]
    assert '"zone":"serp-zone"' in captured[0]["json"]
    assert "https://www.google.com/search?q=Acme+Corp" in captured[0]["json"]
    assert '"format":"json"' in captured[0]["json"]


@pytest.mark.asyncio
async def test_web_unlocker_uses_zone_and_raw_markdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers["authorization"]
        captured["json"] = request.read().decode()
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            text="# Extracted page",
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: async_client(transport=transport))
    client = BrightDataClient(
        Settings(
            mock_mode=False,
            bright_data_api_key="token",
            bright_data_request_endpoint="https://api.brightdata.com/request",
            bright_data_serp_zone="serp-zone",
            bright_data_web_unlocker_zone="unlocker-zone",
        )
    )

    pages = await client.fetch_pages(
        [
            Source(
                title="Source",
                url="https://example.com/article",
                source_type="news",
            )
        ]
    )

    assert pages[0]["content"] == "# Extracted page"
    assert captured["url"] == "https://api.brightdata.com/request"
    assert captured["headers"] == "Bearer token"
    assert '"zone":"unlocker-zone"' in captured["json"]
    assert '"url":"https://example.com/article"' in captured["json"]
    assert '"format":"raw"' in captured["json"]
    assert '"data_format":"markdown"' in captured["json"]


@pytest.mark.parametrize(
    ("payload", "expected_url", "expected_title", "expected_snippet"),
    [
        (
            {
                "organic_results": [
                    {
                        "title": "Organic results item",
                        "url": "https://example.com/organic-results",
                        "description": "Description fallback.",
                    }
                ]
            },
            "https://example.com/organic-results",
            "Organic results item",
            "Description fallback.",
        ),
        (
            {
                "results": [
                    {
                        "link": "https://example.com/results",
                        "snippet": "Snippet from generic results.",
                    }
                ]
            },
            "https://example.com/results",
            "Acme Corp risk query",
            "Snippet from generic results.",
        ),
        (
            {
                "serp": {
                    "organic": [
                        {
                            "title": "Nested SERP item",
                            "link": "https://example.com/nested-serp",
                            "snippet": "Nested snippet.",
                        }
                    ]
                }
            },
            "https://example.com/nested-serp",
            "Nested SERP item",
            "Nested snippet.",
        ),
    ],
)
def test_parse_serp_payload_accepts_bright_data_result_variants(
    payload: dict,
    expected_url: str,
    expected_title: str,
    expected_snippet: str,
) -> None:
    client = BrightDataClient(Settings())

    sources = client._parse_serp_payload(payload, query="Acme Corp risk query")

    assert len(sources) == 1
    assert sources[0].url == expected_url
    assert sources[0].title == expected_title
    assert sources[0].source_type == "serp"
    assert sources[0].snippet == expected_snippet


def test_parse_serp_payload_skips_results_without_urls() -> None:
    client = BrightDataClient(Settings())

    sources = client._parse_serp_payload(
        {
            "organic": [
                {"title": "Missing URL", "snippet": "Should be ignored."},
                {"title": "Valid result", "link": "https://example.com/valid"},
            ]
        },
        query="Acme Corp",
    )

    assert len(sources) == 1
    assert sources[0].url == "https://example.com/valid"


def test_parse_serp_payload_unwraps_bright_data_body_json() -> None:
    client = BrightDataClient(Settings())

    sources = client._parse_serp_payload(
        {
            "status_code": 200,
            "body": (
                '{"organic":[{"title":"Stripe official",'
                '"link":"https://stripe.com","snippet":"Payments infrastructure."}]}'
            ),
        },
        query="Stripe",
    )

    assert len(sources) == 1
    assert sources[0].title == "Stripe official"
    assert sources[0].url == "https://stripe.com"
    assert sources[0].snippet == "Payments infrastructure."


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"content": "# Content markdown", "body": "Body fallback"}, "# Content markdown"),
        ({"body": "Body fallback", "html": "<main>HTML</main>"}, "Body fallback"),
        ({"html": "<main>HTML</main>", "markdown": "# Markdown"}, "<main>HTML</main>"),
        ({"markdown": "# Markdown"}, "# Markdown"),
        ({}, ""),
    ],
)
def test_extract_unlocker_content_reads_json_payload_fields_in_precedence_order(
    payload: dict[str, str],
    expected: str,
) -> None:
    client = BrightDataClient(Settings())
    response = httpx.Response(200, headers={"content-type": "application/json"}, json=payload)

    assert client._extract_unlocker_content(response) == expected
