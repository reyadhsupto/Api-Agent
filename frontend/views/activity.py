# frontend/views/activity.py

"""
Generation Activity view: paged history of generation runs.

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


def render_generation_activity_tab() -> None:
    """Render paged project generation history with full-record details."""
    st.header("Generation activity")
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
