import json
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from app.agent.state import AgentState
from app.config import Settings
from app.schemas import RiskBrief, RiskDimension, RiskRating, Source


class ClaudeSynthesizer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def synthesize(self, state: AgentState) -> RiskBrief:
        if self.settings.mock_mode or not self.settings.anthropic_api_key:
            return self._fixture_brief(state)

        headers = {
            "x-api-key": self.settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.settings.anthropic_model,
            "max_tokens": 2000,
            "temperature": 0.1,
            "system": (
                "You are a vendor due diligence analyst. Return only valid JSON matching "
                "the requested schema. Use cautious, source-cited language."
            ),
            "messages": [{"role": "user", "content": self._build_prompt(state)}],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["content"][0]["text"]

        try:
            return RiskBrief.model_validate_json(content)
        except ValidationError:
            return RiskBrief.model_validate(json.loads(self._extract_json(content)))

    def _build_prompt(self, state: AgentState) -> str:
        request = state["request"]
        previous = state.get("previous_brief")
        context = {
            "company": request.company,
            "domain": request.domain,
            "previous_brief": previous.model_dump(mode="json") if previous else None,
            "search_results": [source.model_dump(mode="json") for source in state["search_results"]],
            "pages": state["pages"],
            "regulatory_findings": state["regulatory_findings"],
            "hiring_signals": state["hiring_signals"],
        }
        return (
            "Return JSON with this shape: {company, assessed_at, overall_rating, "
            "overall_score, dimensions, sources, summary, recommended_action}. Ratings "
            "must be GREEN, AMBER, or RED. Scores are 0-100. Dimensions must include "
            "reputational, financial_health, regulatory_legal, operational_stability, "
            "and supply_chain. Cite source URLs in sources.\n\n"
            f"Context JSON:\n{json.dumps(context, indent=2)}"
        )

    def _fixture_brief(self, state: AgentState) -> RiskBrief:
        request = state["request"]
        sources = state.get("search_results", [])
        regulatory_findings = state.get("regulatory_findings", [])
        previous = state.get("previous_brief")
        has_regulatory_caution = any(
            finding["status"] != "no_match" for finding in regulatory_findings
        )
        regulatory_rating = RiskRating.amber if has_regulatory_caution else RiskRating.green
        regulatory_score = 64 if has_regulatory_caution else 82

        dimensions = {
            "reputational": RiskDimension(
                rating=RiskRating.amber,
                score=68,
                summary="Open-web coverage is mostly neutral, with enough uncertainty to warrant review.",
            ),
            "financial_health": RiskDimension(
                rating=RiskRating.amber,
                score=61,
                summary="Hiring and public operating signals look active but not conclusive.",
            ),
            "regulatory_legal": RiskDimension(
                rating=regulatory_rating,
                score=regulatory_score,
                summary="Fixture checks found no exact sanctions match; live regulatory validation remains required.",
            ),
            "operational_stability": RiskDimension(
                rating=RiskRating.green,
                score=74,
                summary="Website, hiring, and review signals suggest normal operating continuity.",
            ),
            "supply_chain": RiskDimension(
                rating=RiskRating.amber,
                score=58,
                summary="Third-party dependency risk is not fully visible from public fixture data.",
            ),
        }
        overall_score = round(sum(d.score for d in dimensions.values()) / len(dimensions))
        if previous:
            overall_score = max(0, overall_score - 4)
            dimensions["financial_health"].score = max(0, dimensions["financial_health"].score - 6)
            dimensions["financial_health"].summary = (
                "Repeat assessment found slightly weaker hiring confidence in fixture mode."
            )
        overall_rating = (
            RiskRating.red
            if overall_score < 45
            else RiskRating.amber
            if overall_score < 70
            else RiskRating.green
        )
        return RiskBrief(
            company=request.company,
            assessed_at=datetime.now(timezone.utc),
            overall_rating=overall_rating,
            overall_score=overall_score,
            dimensions=dimensions,
            sources=sources
            or [
                Source(
                    title="Fixture source",
                    url="https://example.com",
                    source_type="fixture",
                    snippet="Used when live API credentials are not configured.",
                )
            ],
            summary=(
                f"{request.company} is currently rated {overall_rating}. Public signals are "
                "sufficient for a demo-grade brief, but live source verification is required."
            ),
            recommended_action=(
                "Proceed with standard onboarding, but verify regulatory and supply-chain "
                "findings against live sources before approval."
            ),
        )

    def _extract_json(self, content: str) -> str:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Claude response did not contain a JSON object.")
        return content[start : end + 1]
