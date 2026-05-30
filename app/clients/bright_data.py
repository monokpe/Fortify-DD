import json

import httpx
from urllib.parse import quote_plus

from app.config import Settings
from app.schemas import Source


class BrightDataClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search(self, company: str, domain: str | None = None) -> list[Source]:
        if self.settings.mock_mode:
            return self._mock_search(company, domain)

        if not self.settings.bright_data_api_key or not self.settings.bright_data_serp_zone:
            raise RuntimeError("Bright Data SERP credentials are not configured.")

        queries = [
            company,
            f"{company} news",
            f"{company} legal regulatory sanctions",
            f"{company} Glassdoor reviews",
            f"{company} LinkedIn jobs",
        ]
        if domain:
            queries.append(f"site:{domain} {company}")

        headers = {"Authorization": f"Bearer {self.settings.bright_data_api_key}"}
        results: list[Source] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for query in queries:
                response = await client.post(
                    self.settings.bright_data_request_endpoint,
                    headers=headers,
                    json={
                        "zone": self.settings.bright_data_serp_zone,
                        "url": self._google_search_url(query),
                        "format": "json",
                    },
                )
                response.raise_for_status()
                results.extend(self._parse_serp_payload(response.json(), query))
        return results[:20]

    async def fetch_pages(self, sources: list[Source]) -> list[dict[str, str]]:
        selected = sources[:8]
        if self.settings.mock_mode:
            return [
                {
                    "title": source.title,
                    "url": str(source.url),
                    "content": source.snippet
                    or f"Open-web evidence collected from {source.title}.",
                    "source_type": source.source_type,
                }
                for source in selected
            ]

        if not self.settings.bright_data_api_key or not self.settings.bright_data_web_unlocker_zone:
            raise RuntimeError("Bright Data Web Unlocker credentials are not configured.")

        headers = {"Authorization": f"Bearer {self.settings.bright_data_api_key}"}
        pages: list[dict[str, str]] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for source in selected:
                response = await client.post(
                    self.settings.bright_data_request_endpoint,
                    headers=headers,
                    json={
                        "zone": self.settings.bright_data_web_unlocker_zone,
                        "url": str(source.url),
                        "format": "raw",
                        "data_format": "markdown",
                    },
                )
                response.raise_for_status()
                pages.append(
                    {
                        "title": source.title,
                        "url": str(source.url),
                        "content": self._extract_unlocker_content(response),
                        "source_type": source.source_type,
                    }
                )
        return pages

    async def regulatory_checks(self, company: str) -> list[dict[str, str]]:
        if self.settings.mock_mode:
            return [
                {
                    "source": "OFAC SDN",
                    "status": "no_match",
                    "summary": f"No exact sanctions match found for {company} in fixture mode.",
                    "url": "https://sanctionssearch.ofac.treas.gov/",
                },
                {
                    "source": "SEC EDGAR",
                    "status": "review_recommended",
                    "summary": "No enforcement action identified in fixture mode; verify live source.",
                    "url": "https://www.sec.gov/edgar/search/",
                },
            ]

        return [
            {
                "source": "MCP regulatory checks",
                "status": "not_implemented",
                "summary": "Wire Bright Data MCP Server regulatory navigation here.",
                "url": "https://brightdata.com/products/mcp",
            }
        ]

    async def hiring_signals(self, company: str) -> list[dict[str, str]]:
        if self.settings.mock_mode:
            return [
                {
                    "source": "LinkedIn Jobs",
                    "summary": f"{company} has moderate hiring activity across operations and engineering.",
                    "sentiment": "neutral_positive",
                    "url": "https://www.linkedin.com/jobs/",
                },
                {
                    "source": "Glassdoor",
                    "summary": "Employee review signal is mixed; monitor operational stability.",
                    "sentiment": "mixed",
                    "url": "https://www.glassdoor.com/",
                },
            ]

        return []

    def _google_search_url(self, query: str) -> str:
        return f"https://www.google.com/search?q={quote_plus(query)}"

    def _extract_unlocker_content(self, response: httpx.Response) -> str:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = response.json()
            return (
                payload.get("content")
                or payload.get("body")
                or payload.get("html")
                or payload.get("markdown")
                or ""
            )
        return response.text

    def _mock_search(self, company: str, domain: str | None) -> list[Source]:
        base_domain = domain or f"{company.lower().replace(' ', '')}.com"
        return [
            Source(
                title=f"{company} corporate website",
                url=f"https://{base_domain}",
                source_type="company_site",
                snippet="Official website indicates active operations and customer-facing services.",
            ),
            Source(
                title=f"Recent news about {company}",
                url="https://news.google.com/",
                source_type="news",
                snippet="Recent coverage is mostly neutral with some market uncertainty.",
            ),
            Source(
                title=f"{company} regulatory search",
                url="https://www.sec.gov/edgar/search/",
                source_type="regulatory",
                snippet="Regulatory database search requires live verification.",
            ),
            Source(
                title=f"{company} employee reviews",
                url="https://www.glassdoor.com/",
                source_type="reviews",
                snippet="Public employee sentiment appears mixed in fixture data.",
            ),
            Source(
                title=f"{company} job listings",
                url="https://www.linkedin.com/jobs/",
                source_type="hiring",
                snippet="Hiring activity suggests the company is still operating normally.",
            ),
        ]

    def _parse_serp_payload(self, payload: dict, query: str) -> list[Source]:
        if isinstance(payload.get("body"), str):
            try:
                payload = json.loads(payload["body"])
            except json.JSONDecodeError:
                pass
        organic = (
            payload.get("organic")
            or payload.get("organic_results")
            or payload.get("results")
            or payload.get("serp", {}).get("organic")
            or []
        )
        sources: list[Source] = []
        for item in organic:
            url = item.get("link") or item.get("url")
            if not url:
                continue
            sources.append(
                Source(
                    title=item.get("title") or query,
                    url=url,
                    source_type="serp",
                    snippet=item.get("snippet") or item.get("description"),
                )
            )
        return sources
