from urllib.parse import urlparse

from app.schemas import AssessmentRequest, Source


HIGH_VALUE_DOMAINS = {
    "news.google.com": 4,
    "sec.gov": 7,
    "sanctionssearch.ofac.treas.gov": 8,
    "justice.gov": 7,
    "ftc.gov": 6,
    "fca.org.uk": 6,
    "gov.uk": 5,
    "glassdoor.com": 4,
    "linkedin.com": 4,
}

HIGH_VALUE_TERMS = {
    "sanction": 8,
    "lawsuit": 7,
    "litigation": 7,
    "fraud": 8,
    "investigation": 7,
    "regulatory": 6,
    "enforcement": 7,
    "fine": 5,
    "breach": 6,
    "bankruptcy": 8,
    "insolvency": 8,
    "layoff": 5,
    "reviews": 3,
    "jobs": 3,
    "funding": 3,
}

LOW_VALUE_TERMS = {
    "login": -8,
    "sign in": -8,
    "signup": -7,
    "register": -5,
    "privacy policy": -6,
    "terms of service": -6,
    "cookie": -5,
    "search results": -5,
}

SOURCE_TYPE_WEIGHTS = {
    "regulatory": 10,
    "news": 8,
    "serp": 5,
    "reviews": 4,
    "hiring": 4,
    "company_site": 3,
}


class SourceRanker:
    def rank(
        self,
        sources: list[Source],
        request: AssessmentRequest,
        limit: int = 8,
    ) -> list[Source]:
        deduped = self._dedupe(sources)
        scored = [
            (self.score(source, request), index, source) for index, source in enumerate(deduped)
        ]
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [source for _, _, source in scored[:limit]]

    def score(self, source: Source, request: AssessmentRequest) -> int:
        title = source.title.lower()
        snippet = (source.snippet or "").lower()
        url = str(source.url).lower()
        domain = self._hostname(url)
        haystack = f"{title} {snippet} {url}"

        score = SOURCE_TYPE_WEIGHTS.get(source.source_type, 0)

        company = request.company.lower()
        compact_company = company.replace(" ", "")
        if company in haystack:
            score += 10
        elif compact_company and compact_company in haystack.replace("-", "").replace("_", ""):
            score += 7

        if request.domain and request.domain.lower() in domain:
            score += 6

        for known_domain, weight in HIGH_VALUE_DOMAINS.items():
            if domain == known_domain or domain.endswith(f".{known_domain}"):
                score += weight

        for term, weight in HIGH_VALUE_TERMS.items():
            if term in haystack:
                score += weight

        for term, weight in LOW_VALUE_TERMS.items():
            if term in haystack:
                score += weight

        if url.endswith(".pdf"):
            score += 3
        if len(snippet) > 80:
            score += 2

        return score

    def _dedupe(self, sources: list[Source]) -> list[Source]:
        seen: set[str] = set()
        deduped: list[Source] = []
        for source in sources:
            key = self._normalized_url(str(source.url))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(source)
        return deduped

    def _normalized_url(self, url: str) -> str:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().removeprefix("www.")
        path = parsed.path.rstrip("/")
        return f"{hostname}{path}"

    def _hostname(self, url: str) -> str:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")

