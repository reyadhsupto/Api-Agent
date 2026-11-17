# frontend/views/activity.py

"""
Activity Logs view: generation runs and source-linked Knowledge extraction events.

The route returns one page together with the true record count, as the keys
``activities``, ``total``, ``limit``, and ``offset``. The offset is kept in session
state so paging survives an unrelated widget interaction, and it is clamped
against the reported total so deleting records cannot leave the view on an empty
page.
"""

import streamlit as st

from frontend.core import (
    _normalise_generation_activity_records,
    _show_generation_activity_details,
    api_get,
)

PAGE_SIZES = (10, 25, 50, 100)
DEFAULT_PAGE_SIZE = 25
STATE_COLORS = {"succeeded": "green", "failed": "red", "error": "red"}
EXTRACTION_EVENT_TYPES = {"extracted", "extraction_failed"}
KNOWLEDGE_HUB_EVENT_TYPES = {
    "hub_page_created", "hub_feature_services_updated", "hub_draft_prepared",
    "hub_draft_failed", "hub_update_saved", "hub_version_restored",
}


def render_activity_logs_tab() -> None:
    """Render generation and knowledge extraction histories for the project."""
    st.header("Activity logs")
    view = st.segmented_control(
        "Activity type", ["Generation", "Knowledge Extraction"],
        key=f"activity_logs_view_{(st.session_state.get('current_project') or {}).get('id') or 'none'}",
        label_visibility="collapsed", width="stretch",
    ) or "Generation"
    if view == "Knowledge Extraction":
        _render_knowledge_extraction_logs()
    else:
        _render_generation_logs()


def render_generation_activity_tab() -> None:
    """Compatibility wrapper for callers using the previous view function."""
    render_activity_logs_tab()


def _render_generation_logs() -> None:
    """Render paged project generation history with full-record details."""
    st.subheader("Generation")
    st.caption(
        "Review generation runs by time, type, outcome, and project, then open a row "
        "for its full record."
    )
    project = st.session_state.get("current_project") or {}
    project_id = project.get("id")
    if not project_id:
        st.info("Select a project to view its generation history.")
        return

    size_key = f"activity_page_size_{project_id}"
    offset_key = f"activity_offset_{project_id}"

    toolbar = st.columns([1.1, 1.2, 3], vertical_alignment="bottom")
    page_size = toolbar[0].selectbox(
        "Rows per page", PAGE_SIZES, index=PAGE_SIZES.index(DEFAULT_PAGE_SIZE), key=size_key,
    )
    if toolbar[1].button(
        "Refresh", icon=":material/refresh:", width="stretch",
        key=f"activity_refresh_{project_id}",
    ):
        st.session_state[offset_key] = 0
        st.rerun()

    offset = max(0, int(st.session_state.get(offset_key) or 0))
    try:
        payload = api_get(
            f"/api/v1/projects/{project_id}/generation-activity"
            f"?limit={int(page_size)}&offset={offset}"
        )
    except Exception as exc:
        st.error(f"Could not load generation history: {exc}")
        return
    records = _normalise_generation_activity_records(payload)
    total = payload.get("total") if isinstance(payload, dict) else None
    if not isinstance(total, int):
        total = offset + len(records)

    pages = max(1, (total + page_size - 1) // page_size)
    page = offset // page_size + 1
    if total and offset >= total:
        st.session_state[offset_key] = max(0, (pages - 1) * page_size)
        st.rerun()

    if not records:
        st.info("No generation activity is recorded for this project yet.")
        return

    project_name = project.get("name") or "Unnamed project"
    superseded = {
        str(item.get("supersedes_activity_id")) for item in records
        if item.get("supersedes_activity_id")
    }
    with st.container(key=f"generation-activity-table-{project_id}"):
        head = st.columns([2.1, 1.3, 1.1, 1.9, 0.9], vertical_alignment="center")
        for column, label in zip(
            head, ("Execution time", "Generation type", "State", "Project", "Action")
        ):
            column.markdown(f"**{label}**")
        for record in records:
            with st.container(border=True):
                cells = st.columns([2.1, 1.3, 1.1, 1.9, 0.9], vertical_alignment="center")
                stamp = str(record.get("created_at") or "Unknown")
                cells[0].write(stamp.replace("T", " ")[:19])
                cells[1].write(record.get("mode") or "Generation")
                state = str(record.get("status") or "unknown").capitalize()
                if str(record.get("id")) in superseded:
                    state = "Superseded"
                color = STATE_COLORS.get(state.lower(), "gray")
                cells[2].markdown(f":{color}-badge[{state}]")
                cells[3].write(project_name)
                cells[3].caption(str(record.get("project_id") or project_id))
                if cells[4].button(
                    "View", icon=":material/visibility:", width="stretch",
                    key=f"view_generation_activity_{record['id']}",
                ):
                    _show_generation_activity_details(record)

        st.divider()
        previous_col, info_col, next_col = st.columns([1, 2, 1], vertical_alignment="center")
        if previous_col.button(
            "Previous", icon=":material/chevron_left:", width="stretch",
            key=f"activity_prev_{project_id}", disabled=page <= 1,
        ):
            st.session_state[offset_key] = max(0, (page - 2) * page_size)
            st.rerun()
        info_col.markdown(
            f":gray-badge[Page {page} of {pages}] :gray-badge[{total} record(s)]"
        )
        if next_col.button(
            "Next", icon=":material/chevron_right:", width="stretch",
            key=f"activity_next_{project_id}", disabled=page >= pages,
        ):
            st.session_state[offset_key] = page * page_size
            st.rerun()


@st.dialog("Knowledge extraction details", width="large")
def _show_extraction_details(event: dict, submission: dict) -> None:
    """Show the retained source and output from one extraction attempt."""
    payload = event.get("payload") or {}
    if event.get("event_type") in KNOWLEDGE_HUB_EVENT_TYPES:
        _show_knowledge_hub_event_details(event, payload)
        return
    failed = event.get("event_type") == "extraction_failed"
    state = "Failed" if failed else "Completed"
    st.caption(
        f"{str(event.get('created_at') or 'Unknown time').replace('T', ' ')[:19]} · "
        f"{submission.get('source_type') or 'source'} · {state}"
    )
    st.caption(f"Source: {submission.get('source_name') or 'Untitled source'}")
    st.caption(f"Submission ID: {event.get('submission_id') or 'Unknown'}")
    provider_metadata = payload.get("provider_metadata") or {}
    if provider_metadata:
        usage = provider_metadata.get("usage") or {}
        st.caption(
            f"Provider: {provider_metadata.get('provider') or 'unknown'} · "
            f"Model: {provider_metadata.get('model') or 'unknown'} · "
            f"Finish reason: {provider_metadata.get('finish_reason') or 'not reported'}"
        )
        if usage:
            st.caption(
                f"Tokens · prompt {usage.get('prompt_tokens', '?')} · "
                f"completion {usage.get('completion_tokens', '?')} · total {usage.get('total_tokens', '?')}"
            )
        if provider_metadata.get("finish_reason") == "length":
            st.warning("The model hit its output token limit. The response below is incomplete; retry extraction.")
    if failed:
        st.error(str(payload.get("error") or submission.get("extraction_error") or "Extraction failed."))
    raw_response = str(payload.get("raw_response") or "")
    with st.expander("Raw model response", expanded=failed and bool(raw_response)):
        if raw_response:
            st.code(raw_response, language="text")
        else:
            st.caption("No raw model response was retained for this attempt. Retry extraction to capture it.")
    if payload.get("gist"):
        st.markdown("**Extraction summary**")
        st.write(payload["gist"])
    proposals = payload.get("proposals") or []
    if proposals:
        st.markdown(f"**Proposed facts ({len(proposals)})**")
        for proposal in proposals:
            st.markdown(f"**{proposal.get('title') or 'Proposed fact'}** · {proposal.get('operation', 'add')}")
            st.write(proposal.get("content") or "")
            if proposal.get("evidence_quote"):
                st.caption(f"Evidence: “{proposal['evidence_quote']}”")
    for label, key in (("Conflicts", "conflicts"), ("Open questions", "questions")):
        values = payload.get(key) or []
        if values:
            st.markdown(f"**{label}**")
            for value in values:
                st.write(value)
    prompt_messages = payload.get("prompt_messages") or []
    with st.expander("Prompt sent to the extraction model", expanded=False):
        if prompt_messages:
            for message in prompt_messages:
                st.markdown(f"**{str(message.get('role') or 'message').title()}**")
                st.code(str(message.get("content") or ""), language="text")
        else:
            st.caption("The prompt was not retained for this older extraction attempt.")
    with st.expander("Original source text", expanded=False):
        st.text(submission.get("source_text") or "")


def _show_knowledge_hub_event_details(event: dict, payload: dict) -> None:
    """Render the prompt, response, version, and provenance for a Hub action."""
    labels = {
        "hub_page_created": "Page created",
        "hub_feature_services_updated": "Feature services changed",
        "hub_draft_prepared": "Knowledge update drafted",
        "hub_draft_failed": "Knowledge update draft failed",
        "hub_update_saved": "Knowledge pages saved",
        "hub_version_restored": "Page version restored",
    }
    event_type = str(event.get("event_type") or "")
    failed = event_type == "hub_draft_failed"
    st.caption(
        f"{str(event.get('created_at') or 'Unknown time').replace('T', ' ')[:19]} · "
        f"{labels.get(event_type, 'Knowledge Hub activity')} · "
        f"{'Failed' if failed else payload.get('status') or 'Recorded'}"
    )
    if payload.get("source_thread_id"):
        st.caption(f"Source chat thread: {payload['source_thread_id']}")
    if payload.get("draft_event_id"):
        st.caption(f"Prepared draft activity: {payload['draft_event_id']}")
    if payload.get("error"):
        st.error(str(payload["error"]))

    pages = payload.get("pages") or []
    if not pages and any(payload.get(key) for key in ("scope_id", "scope_name", "content")):
        pages = [payload]
    for index, page in enumerate(pages):
        page_label = str(page.get("scope_name") or page.get("name") or page.get("scope_id") or f"Page {index + 1}")
        if page.get("scope_type"):
            page_label += f" · {page['scope_type']}"
        if page.get("version_number"):
            page_label += f" · v{page['version_number']}"
        with st.expander(page_label, expanded=failed):
            if page.get("error"):
                st.error(str(page["error"]))
            if page.get("provider_metadata"):
                metadata = page["provider_metadata"]
                st.caption(
                    f"Provider: {metadata.get('provider') or 'unknown'} · "
                    f"Model: {metadata.get('model') or 'unknown'}"
                )
            content = str(page.get("content") or "")
            if content:
                st.markdown("**Saved page content**")
                st.markdown(content)
            prompt_messages = page.get("prompt_messages") or []
            if prompt_messages:
                with st.expander("Prompt sent to the model", expanded=False):
                    for message in prompt_messages:
                        st.markdown(f"**{str(message.get('role') or 'message').title()}**")
                        st.code(str(message.get("content") or ""), language="text")
            if "raw_response" in page:
                with st.expander("Raw model response", expanded=failed and bool(page.get("raw_response"))):
                    st.code(str(page.get("raw_response") or "No response captured."), language="text")
            if page.get("previous_microservices") is not None:
                st.markdown("**Previous microservices**")
                st.write([item.get("name") for item in page.get("previous_microservices", [])] or "None")
                st.markdown("**Current microservices**")
                st.write([item.get("name") for item in page.get("microservices", [])] or "None")
    if not pages:
        st.json(payload)


def _render_knowledge_extraction_logs() -> None:
    """Render extraction attempts and append-only Knowledge Hub activity."""
    st.subheader("Knowledge extraction")
    st.caption(
        "Review historical extraction attempts alongside Knowledge Hub drafts, page saves, "
        "restores, and feature-service changes. Open a row for prompts, model responses, and details."
    )
    project = st.session_state.get("current_project") or {}
    project_id = project.get("id")
    if not project_id:
        st.info("Select a project to view knowledge extraction logs.")
        return
    if st.button(
        "Refresh", icon=":material/refresh:", key=f"knowledge_activity_refresh_{project_id}",
    ):
        st.session_state[f"knowledge_activity_offset_{project_id}"] = 0
        st.rerun()

    size_key = f"knowledge_activity_page_size_{project_id}"
    offset_key = f"knowledge_activity_offset_{project_id}"
    page_size = st.selectbox(
        "Rows per page", PAGE_SIZES, index=PAGE_SIZES.index(DEFAULT_PAGE_SIZE), key=size_key,
    )
    offset = max(0, int(st.session_state.get(offset_key) or 0))
    try:
        activity = api_get(
            f"/api/v1/projects/{project_id}/knowledge/activity"
            f"?limit={int(page_size)}&offset={offset}"
        ) or {}
    except Exception as exc:
        st.error(f"Could not load knowledge activity logs: {exc}")
        return
    total = int(activity.get("total") or 0)
    pages = max(1, (total + page_size - 1) // page_size)
    if total and offset >= total:
        offset = max(0, (pages - 1) * page_size)
        st.session_state[offset_key] = offset
        st.rerun()
    attempts = activity.get("events") or []
    if not total:
        st.info("No knowledge extraction or Knowledge Hub activity is recorded for this project yet.")
        return
    page = offset // page_size + 1

    with st.container(key=f"knowledge-extraction-log-{project_id}"):
        head = st.columns([1.8, 2.2, 1.2, 1.1, 0.8], vertical_alignment="center")
        for column, label in zip(head, ("Time", "Activity", "Outcome", "Pages / proposals", "Details")):
            column.markdown(f"**{label}**")
        for index, event in enumerate(attempts):
            event_type = str(event.get("event_type") or "")
            is_hub_event = event_type in KNOWLEDGE_HUB_EVENT_TYPES
            failed = event_type in {"extraction_failed", "hub_draft_failed"}
            summary = event.get("summary") or {}
            stamp = str(event.get("created_at") or "Unknown")
            source_type = str(event.get("source_type") or "source").replace("_", " ").title()
            source_name = str(event.get("source_name") or "Untitled source")
            hub_labels = {
                "hub_page_created": "Knowledge Hub · Page created",
                "hub_feature_services_updated": "Knowledge Hub · Service links updated",
                "hub_draft_prepared": "Knowledge Hub · Draft prepared",
                "hub_draft_failed": "Knowledge Hub · Draft failed",
                "hub_update_saved": "Knowledge Hub · Pages saved",
                "hub_version_restored": "Knowledge Hub · Version restored",
            }
            activity_label = hub_labels.get(event_type, source_name)
            page_names = summary.get("page_names") or []
            item_count = summary.get("page_count", 0) if is_hub_event else summary.get("proposal_count", 0)
            with st.container(border=True):
                cells = st.columns([1.8, 2.2, 1.2, 1.1, 0.8], vertical_alignment="center")
                cells[0].write(stamp.replace("T", " ")[:19])
                cells[1].write(activity_label)
                if not is_hub_event:
                    cells[1].caption(source_type)
                elif page_names:
                    cells[1].caption(", ".join(page_names))
                if failed:
                    cells[2].markdown(":red-badge[Failed]")
                elif is_hub_event and event_type not in {"hub_draft_prepared"}:
                    cells[2].markdown(":gray-badge[Recorded]")
                else:
                    cells[2].markdown(":green-badge[Completed]")
                cells[3].write(str(item_count))
                if cells[4].button(
                    "View", icon=":material/visibility:", width="stretch",
                    key=f"view_extraction_event_{project_id}_{event.get('id') or index}",
                ):
                    try:
                        detail = api_get(
                            f"/api/v1/projects/{project_id}/knowledge/activity/{event['id']}"
                        ) or {}
                        _show_extraction_details(detail, detail.get("submission") or {})
                    except Exception as exc:
                        st.error(f"Could not load knowledge activity details: {exc}")

    st.divider()
    previous_col, info_col, next_col = st.columns([1, 2, 1], vertical_alignment="center")
    if previous_col.button(
        "Previous", icon=":material/chevron_left:", width="stretch",
        key=f"knowledge_activity_prev_{project_id}", disabled=page <= 1,
    ):
        st.session_state[offset_key] = max(0, (page - 2) * page_size)
        st.rerun()
    info_col.markdown(
        f":gray-badge[Page {page} of {pages}] :gray-badge[{total} activity record(s)]"
    )
    if next_col.button(
        "Next", icon=":material/chevron_right:", width="stretch",
        key=f"knowledge_activity_next_{project_id}", disabled=page >= pages,
    ):
        st.session_state[offset_key] = page * page_size
        st.rerun()
