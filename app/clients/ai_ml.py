import json

import httpx

from app.config import Settings
from app.schemas import AssessmentRequest, Source
from app.services.source_ranker import SourceRanker


class AIMLRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.fallback_ranker = SourceRanker()

    async def triage_sources(
        self,
        sources: list[Source],
        request: AssessmentRequest,
        limit: int = 8,
    ) -> list[Source]:
        if self.settings.mock_mode or not self.settings.aiml_api_key:
            return self.fallback_ranker.rank(sources, request=request, limit=limit)

        headers = {
            "Authorization": f"Bearer {self.settings.aiml_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.aiml_triage_model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Rank vendor due diligence sources by relevance. Return only JSON "
                        "with a ranked_indices array of zero-based source indices."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "company": request.company,
                            "domain": request.domain,
                            "sources": [
                                {
                                    "index": index,
                                    "title": source.title,
                                    "url": str(source.url),
                                    "source_type": source.source_type,
                                    "snippet": source.snippet,
                                }
                                for index, source in enumerate(sources)
                            ],
                        }
                    ),
                },
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{self.settings.aiml_base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                ranked_indices = self._parse_ranked_indices(response.json())
        except httpx.HTTPError:
            return self.fallback_ranker.rank(sources, request=request, limit=limit)

        ranked: list[Source] = []
        seen: set[int] = set()
        for index in ranked_indices:
            if 0 <= index < len(sources) and index not in seen:
                ranked.append(sources[index])
                seen.add(index)
            if len(ranked) >= limit:
                return ranked

        for source in self.fallback_ranker.rank(sources, request=request, limit=limit):
            if source not in ranked:
                ranked.append(source)
            if len(ranked) >= limit:
                break
        return ranked

    def _parse_ranked_indices(self, payload: dict) -> list[int]:
        content = (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return []
        indices = parsed.get("ranked_indices", [])
        ranked_indices: list[int] = []
        for index in indices:
            if not isinstance(index, int | str):
                continue
            try:
                ranked_indices.append(int(index))
            except ValueError:
                continue
        return ranked_indices
