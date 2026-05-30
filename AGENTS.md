# AGENTS.md

## Project

Fortify DD is an AI-powered autonomous due diligence agent for vendor risk assessment. The MVP takes a company name and optional domain, gathers live open-web intelligence, and returns a structured red / amber / green risk brief in under 60 seconds.

Version 2.0 upgrades the product from a one-shot assessment tool into a continuous, event-driven compliance monitoring system: Fortify DD remembers prior assessments, detects vendor risk drift, and triggers alerts when risk changes.

The source product requirements are in `Fortify_DD_PRD_v2.docx`. This v2 PRD supersedes `Fortify_DD_PRD.docx`.

## Product Priorities

- Build a working end-to-end demo: company name in, cited risk brief out.
- Keep Bright Data integrations load-bearing, especially SERP API, Web Unlocker, and MCP Server.
- Treat Cognee memory and TriggerWare alerting as first-class v2 MVP capabilities, not optional polish.
- Prefer reliable structured output, risk deltas, and cited evidence over broad feature coverage.
- Optimize for hackathon demo clarity: visible pipeline progress, readable one-page brief, delta report, alert event, and source citations.
- Use AI/ML API for fast model routing where it improves latency or demo credibility.
- Keep Speechmatics voice readout as a stretch goal for RED alerts after the core pipeline is stable.
- Preserve a path to a real B2B SaaS product after the hackathon.

## Expected Stack

- Backend: Python 3.11+ with FastAPI.
- Agent orchestration: LangGraph.
- LLM synthesis: Claude Sonnet, producing validated structured JSON.
- Fast triage / auxiliary models: AI/ML API, especially Llama 3.1 8B for SERP relevance ranking and lightweight comparison tasks.
- Web data: Bright Data SERP API, Web Unlocker, and MCP Server.
- Agent memory: Cognee for persistent vendor knowledge, prior briefs, risk history, and entity relationships.
- Event automation: TriggerWare.ai for scheduled monitoring and downstream risk-change actions.
- Voice layer: Speechmatics TTS for spoken RED-alert summaries, if time permits.
- Demo frontend: React + Tailwind preferred; Streamlit is acceptable only if it materially improves build speed.
- Async execution: FastAPI background tasks or native `asyncio` for the MVP.

## Core MVP Endpoints

- `POST /assess`: submit a company assessment request and trigger the full pipeline.
- `GET /assess/{task_id}`: poll for assessment status and results.
- `GET /vendor/{name}/history`: retrieve historical briefs and risk drift from Cognee.
- `POST /watchlist`: subscribe a vendor for scheduled monitoring.
- `POST /webhook/trigger`: TriggerWare polling endpoint that returns a diff payload.
- `GET /health`: service health check.

## Agent Pipeline

Recommended LangGraph node sequence:

1. `memory_query_node`: query Cognee for previous briefs, risk history, and known entity relationships.
2. `start_node`: validate input, create `task_id`, and initialize state with Cognee context.
3. `triage_node`: use AI/ML API to score and rank SERP results for relevance.
4. `serp_node`: query company, news, legal, social, and review results with Bright Data SERP API.
5. `fetch_node`: fetch relevant page content through Bright Data Web Unlocker.
6. `sanctions_node`: check sanctions, regulatory, EDGAR, Companies House, and similar sources through Bright Data MCP.
7. `hiring_node`: gather hiring, review, and employee-signal data.
8. `synthesise_node`: ask Claude Sonnet to produce validated structured risk output.
9. `compare_node`: compare current findings with prior Cognee memory and produce a delta summary when prior history exists.
10. `store_memory_node`: store the full risk brief, citations, timestamp, and relationships in Cognee.
11. `output_node`: format and return the risk brief; if rating changed, prepare TriggerWare webhook payload; if RED and Speechmatics is enabled, generate audio.

TriggerWare sits outside the graph as the event consumer for watchlist polling and downstream alert routing.

## Risk Dimensions

The risk brief should score and summarize:

- Reputational risk.
- Financial health signals.
- Regulatory and legal exposure.
- Operational stability.
- Supply chain / third-party risk.

## Output Contracts

- Structured JSON risk brief with overall rating, five risk dimensions, evidence, source URLs, narrative summary, and recommended action.
- Delta report when prior memory exists: previous rating, current rating, changed dimensions, and drift narrative.
- TriggerWare webhook payload: `vendor`, `prev_rating`, `new_rating`, `dimensions_changed`, and `summary`.
- Speechmatics audio URL only for RED alerts when the voice layer is enabled.

## Engineering Guidelines

- Use Pydantic models for all request, response, webhook, memory, and LLM output contracts.
- Validate and repair LLM output before returning it from the API.
- Keep API clients isolated from agent node logic.
- Keep Bright Data, Cognee, TriggerWare, AI/ML API, Anthropic, and Speechmatics integrations behind small client modules.
- Add mock or fixture mode early so the demo can run if live APIs fail.
- Keep source URLs with extracted evidence throughout the pipeline and store them with Cognee memory.
- Do not lose historical context: prior briefs, deltas, and rating changes are part of the v2 product.
- Avoid adding production auth, billing, or multi-tenancy until the MVP flow works.
- Prefer small, testable modules over large agent functions.

## Demo Reliability

- Test with at least five companies before submission.
- Test the same vendor twice to prove Cognee memory and risk-drift comparison work.
- Test a simulated rating change that causes TriggerWare to fire.
- Cache successful demo runs when practical.
- Keep the UI focused on input, visible node-by-node progress, final rating, risk dimensions, delta report, alert status, and citations.
- Do not add Speechmatics or extra alert destinations until the core pipeline, memory, and TriggerWare flow are stable.
- Record a backup video demo once the assessment-plus-alert path works.
- Do not add new features after the core pipeline and demo are stable.

## Non-Goals For Initial MVP

- Full production authentication.
- Multi-tenant SaaS administration.
- Persistent assessment history outside the minimal Cognee-backed memory required for v2.
- Complex dashboards.
- Billing or tenant management.
- Broad alert destination support beyond the demo TriggerWare workflow.
- White-label portals.
