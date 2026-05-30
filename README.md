# Fortify DD

Bulletproof due diligence in seconds.

Fortify DD is an AI-powered vendor due diligence agent. The MVP accepts a company name, gathers open-web and regulatory signals, and returns a structured red / amber / green risk brief with source citations.

The product requirements live in `Fortify_DD_PRD_v2.docx`.

## Current Status

This is the first backend scaffold:

- FastAPI app with `/health`, `/assess`, `/assess/{task_id}`, `/vendor/{name}/history`, `/watchlist`, `/webhook/trigger`, and `/triggerware/poll`.
- Pydantic request, response, risk brief, delta, watchlist, and alert schemas.
- In-memory async assessment task store.
- Due diligence pipeline matching the v2 PRD stages.
- Bright Data SERP, Web Unlocker, and regulatory client placeholders.
- Claude synthesis client with fixture mode fallback.
- AI/ML API triage client with deterministic source-ranker fallback.
- Cognee-style in-memory vendor history for fixture mode.
- TriggerWare alert payload generation and webhook client.
- Speechmatics audio URL generation for RED alerts in fixture mode.

Fixture mode is enabled by default so the API can run before live credentials are configured.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,demo]"
Copy-Item .env.example .env
```

Then run:

```powershell
uvicorn app.main:app --reload
```

Open the API docs at:

```text
http://127.0.0.1:8000/docs
```

## Demo UI

In a second terminal, run:

```powershell
streamlit run demo_app.py
```

The demo UI expects the FastAPI server to be available at:

```text
http://127.0.0.1:8000
```

## Example Request

```powershell
$response = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/assess -ContentType "application/json" -Body '{"company":"Acme Corp","domain":"acme.com"}'
$response
Invoke-RestMethod -Uri "http://127.0.0.1:8000/assess/$($response.task_id)"
```

## Environment

See `.env.example`.

Key settings:

- `MOCK_MODE=true`: use deterministic fixture data.
- `ANTHROPIC_API_KEY`: enables live Claude synthesis when `MOCK_MODE=false`.
- `ANTHROPIC_MODEL`: Claude model used for risk synthesis. Defaults to `claude-sonnet-4-20250514`.
- `AIML_API_KEY`: enables live AI/ML API SERP triage when `MOCK_MODE=false`.
- `AIML_TRIAGE_MODEL`: fast model used for source ranking.
- `BRIGHT_DATA_API_KEY`: enables live Bright Data calls when `MOCK_MODE=false`.
- `BRIGHT_DATA_REQUEST_ENDPOINT`: Bright Data request endpoint. Defaults to `https://api.brightdata.com/request`.
- `BRIGHT_DATA_SERP_ZONE`: Bright Data SERP API zone name.
- `BRIGHT_DATA_WEB_UNLOCKER_ZONE`: Bright Data Web Unlocker zone name.
- `BRIGHT_DATA_MCP_TOKEN`: token for future Bright Data MCP Server integration.
- `COGNEE_API_URL` and `COGNEE_API_KEY`: reserved for live Cognee memory integration.
- `TRIGGERWARE_WEBHOOK_URL`: optional downstream TriggerWare webhook destination.
- `SPEECHMATICS_API_KEY`: enables live Speechmatics voice generation when wired.

## Deploying to Vercel

This repository is configured for Vercel's Python runtime. Vercel should detect
the root `index.py` entrypoint, which re-exports the FastAPI app from
`app.main:app`.

Recommended first deployment:

1. Import the GitHub repository in Vercel.
2. Keep the project root as the repository root.
3. Leave build and output settings empty so Vercel uses the Python preset.
4. Add environment variables:

```text
APP_ENV=production
MOCK_MODE=true
```

For a live-data deployment, set `MOCK_MODE=false` and add the API keys from
`.env.example`.

Useful smoke tests after deployment:

```powershell
Invoke-RestMethod https://your-project.vercel.app/health
Invoke-RestMethod -Method Post -Uri https://your-project.vercel.app/webhook/trigger -ContentType "application/json" -Body '{"company":"Acme Corp","domain":"acme.com"}'
```

The inline trigger endpoints are the safest Vercel demo path because they complete
inside a single request. The `/assess` polling flow currently uses in-memory
background task state, which is suitable for local demos but should move to durable
storage before relying on it in serverless production.

## Bright Data Integration

Both SERP API and Web Unlocker use Bright Data's shared request endpoint:

```text
https://api.brightdata.com/request
```

SERP requests send a Google search URL with the SERP zone:

```json
{
  "zone": "your-serp-zone",
  "url": "https://www.google.com/search?q=acme+corp+news",
  "format": "json"
}
```

Web Unlocker requests send the target page URL with the unlocker zone:

```json
{
  "zone": "your-web-unlocker-zone",
  "url": "https://example.com/article",
  "format": "raw",
  "data_format": "markdown"
}
```

## v2 Demo Flow

1. Run `/assess` for a vendor and show the baseline risk brief.
2. Run the same vendor again, call `/webhook/trigger`, or poll `/triggerware/poll` to show Cognee-backed memory retrieval and a delta report.
3. Add the vendor to `/watchlist` to show the TriggerWare monitoring surface.
4. Use the Streamlit UI to show node-by-node progress, risk dimensions, citations, drift, and alert status.

## Next Build Steps

1. Replace regulatory placeholder with Bright Data MCP Server navigation.
2. Replace the in-memory Cognee adapter with the live Cognee API.
3. Add cached demo fixtures from successful live runs.
4. Tune AI/ML API triage and source-ranking weights using live Bright Data results from 5+ demo companies.
5. Wire live Speechmatics audio generation once the assessment-plus-alert path is stable.
