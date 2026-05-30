import time
from typing import Any

import httpx
import streamlit as st


API_BASE_URL = "http://127.0.0.1:8000"

STAGE_LABELS = {
    "queued": "Queued",
    "memory": "Cognee memory",
    "serp": "SERP intelligence",
    "triage": "AI/ML triage",
    "fetch": "Deep page extraction",
    "regulatory": "Sanctions and regulatory checks",
    "hiring": "Hiring and review signals",
    "synthesis": "Risk synthesis",
    "compare": "Risk drift comparison",
    "store_memory": "Store memory",
    "alert": "Alert routing",
    "complete": "Complete",
    "failed": "Failed",
}

STAGE_ORDER = [
    "queued",
    "memory",
    "serp",
    "triage",
    "fetch",
    "regulatory",
    "hiring",
    "synthesis",
    "compare",
    "store_memory",
    "alert",
    "complete",
]
RATING_COLORS = {"GREEN": "#0f8a5f", "AMBER": "#b7791f", "RED": "#c53030"}


def post_assessment(company: str, domain: str | None) -> dict[str, Any]:
    payload: dict[str, str] = {"company": company}
    if domain:
        payload["domain"] = domain
    response = httpx.post(f"{API_BASE_URL}/assess", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def post_watchlist(company: str, domain: str | None) -> dict[str, Any]:
    payload: dict[str, str] = {"company": company, "schedule": "daily"}
    if domain:
        payload["domain"] = domain
    response = httpx.post(f"{API_BASE_URL}/watchlist", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def get_assessment(task_id: str) -> dict[str, Any]:
    response = httpx.get(f"{API_BASE_URL}/assess/{task_id}", timeout=10)
    response.raise_for_status()
    return response.json()


def render_stage(stage: str) -> None:
    active_index = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else 0
    labels = []
    for index, step in enumerate(STAGE_ORDER):
        marker = "[x]" if index < active_index or stage == "complete" else "-"
        if index == active_index and stage != "complete":
            marker = ">"
        labels.append(f"{marker} {STAGE_LABELS[step]}")
    st.caption("   ".join(labels))
    denominator = max(len(STAGE_ORDER) - 1, 1)
    st.progress(min(active_index / denominator, 1.0))


def render_rating(label: str, rating: str, score: int) -> None:
    color = RATING_COLORS.get(rating, "#4a5568")
    st.markdown(
        f"""
        <div class="rating-pill" style="border-color:{color}; color:{color};">
          <span>{label}</span>
          <strong>{rating}</strong>
          <span>{score}/100</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_delta(delta: dict[str, Any] | None) -> None:
    if not delta:
        return
    st.markdown("#### Risk drift")
    cols = st.columns(3)
    cols[0].metric("Previous", delta.get("previous_rating") or "Baseline")
    cols[1].metric("Current", delta["current_rating"])
    cols[2].metric("Changed dimensions", len(delta.get("changed_dimensions") or []))
    st.write(delta["summary"])
    if delta.get("changed_dimensions"):
        changed = ", ".join(name.replace("_", " ").title() for name in delta["changed_dimensions"])
        st.caption(changed)


def render_alert(alert: dict[str, Any] | None, audio_url: str | None) -> None:
    if not alert:
        return
    st.markdown("#### Alert")
    if alert["rating_changed"]:
        st.warning(alert["summary"])
    else:
        st.info("No rating change detected. TriggerWare would stay quiet.")
    if audio_url or alert.get("audio_url"):
        st.audio(audio_url or alert["audio_url"])


def render_brief(result: dict[str, Any]) -> None:
    brief = result["risk_brief"]
    rating = brief["overall_rating"]
    score = brief["overall_score"]
    st.markdown("### Risk brief")
    render_rating("Overall", rating, score)
    if brief.get("summary"):
        st.write(brief["summary"])

    render_delta(result.get("delta"))
    render_alert(result.get("alert"), result.get("audio_url"))

    st.markdown("#### Dimensions")
    for key, dimension in brief["dimensions"].items():
        title = key.replace("_", " ").title()
        with st.container(border=True):
            render_rating(title, dimension["rating"], dimension["score"])
            st.write(dimension["summary"])

    st.markdown("#### Recommended action")
    st.info(brief["recommended_action"])

    st.markdown("#### Sources")
    for source in brief["sources"]:
        st.markdown(f"- [{source['title']}]({source['url']}) - `{source['source_type']}`")
        if source.get("snippet"):
            st.caption(source["snippet"])


def main() -> None:
    st.set_page_config(page_title="Fortify DD", page_icon="F", layout="wide")
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2rem; max-width: 1180px; }
        .rating-pill {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            border: 1px solid;
            border-radius: 8px;
            padding: 0.65rem 0.85rem;
            margin-bottom: 0.65rem;
            background: #ffffff;
        }
        .rating-pill span, .rating-pill strong { font-size: 0.95rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("Fortify DD")
    st.caption("Bulletproof due diligence in seconds.")

    with st.sidebar:
        st.subheader("Connection")
        st.code(API_BASE_URL)
        try:
            health = httpx.get(f"{API_BASE_URL}/health", timeout=3).json()
            st.success(f"API online - mock mode: {health['mock_mode']}")
        except Exception:
            st.error("API offline. Start FastAPI before running an assessment.")

    with st.form("assessment_form"):
        col1, col2 = st.columns([2, 1])
        company = col1.text_input("Company", placeholder="Acme Corp")
        domain = col2.text_input("Domain", placeholder="acme.com")
        assess, watch = st.columns([1, 1])
        submitted = assess.form_submit_button("Run assessment", type="primary")
        watchlisted = watch.form_submit_button("Add to watchlist")

    if submitted or watchlisted:
        if not company.strip():
            st.warning("Enter a company name to start.")
            return
        if watchlisted:
            try:
                entry = post_watchlist(company.strip(), domain.strip() or None)
                st.success(f"Watching {entry['vendor']} on a {entry['schedule']} schedule.")
            except Exception as exc:
                st.error(f"Could not add watchlist entry: {exc}")
                return
        if submitted:
            try:
                created = post_assessment(company.strip(), domain.strip() or None)
                st.session_state["task_id"] = created["task_id"]
                st.session_state["last_result"] = None
            except Exception as exc:
                st.error(f"Could not start assessment: {exc}")
                return

    task_id = st.session_state.get("task_id")
    if not task_id:
        st.write("Enter a company and run an assessment to generate a risk brief.")
        return

    result_slot = st.empty()
    for _ in range(60):
        try:
            result = get_assessment(task_id)
            st.session_state["last_result"] = result
        except Exception as exc:
            result_slot.error(f"Could not fetch assessment: {exc}")
            return

        with result_slot.container():
            st.caption(f"Task `{task_id}`")
            render_stage(result["stage"])
            if result["status"] == "failed":
                st.error(result.get("error") or "Assessment failed.")
                return
            if result["status"] == "complete" and result.get("risk_brief"):
                render_brief(result)
                return

        time.sleep(1)

    st.warning("Assessment is still running. Refresh or poll the API for the final result.")


if __name__ == "__main__":
    main()
