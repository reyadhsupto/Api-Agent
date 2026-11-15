# frontend/views/activity.py

"""
Generation Activity view: history of generation runs with full records.
"""

import streamlit as st

import html

from frontend.core import (
    _normalise_generation_activity_records,
    _show_generation_activity_details,
    api_get,
)


def render_generation_activity_tab() -> None:
    """Render project generation history, including exact prompts and responses."""
    st.header("Generation activity")
    st.caption("Review generation runs by time, type, outcome, and project. Open a row for its full record.")
    project = st.session_state.get("current_project") or {}
    project_id = project.get("id")
    if not project_id:
        st.info("Select a project to view its generation history.")
        return
    cache_key = f"generation_activity_{project_id}"
    refresh_key = f"refresh_generation_activity_{project_id}"
    refresh_clicked = st.button("Refresh logs", key=refresh_key, icon=":material/refresh:")
    if cache_key not in st.session_state or refresh_clicked:
        try:
            st.session_state[cache_key] = api_get(
                f"/api/v1/projects/{project_id}/generation-activity?limit=100"
            )
        except Exception as exc:
            st.error(f"Could not load generation history: {exc}")
    records = _normalise_generation_activity_records(st.session_state.get(cache_key))
    if not records:
        st.info("No generation activity is recorded for this project yet.")
        return

    project_name = project.get("name") or "Unnamed project"
    superseded_activity_ids = {
        str(item.get("supersedes_activity_id")) for item in records
        if item.get("supersedes_activity_id")
    }
    with st.container(key=f"generation-activity-table-{project_id}"):
        header = st.columns([2.2, 1.2, 1.0, 1.7, 1.0], vertical_alignment="center")
        for column, title in zip(header, ("Execution time", "Generation type", "State", "Project", "Action")):
            with column:
                st.markdown(f"**{title}**")
        for record in records:
            with st.container(border=True):
                columns = st.columns([2.2, 1.2, 1.0, 1.7, 1.0], vertical_alignment="center")
                with columns[0]:
                    raw_time = str(record.get("created_at") or "Unknown")
                    st.write(raw_time.replace("T", " ")[:19])
                with columns[1]:
                    st.write(record.get("mode") or "Generation")
                with columns[2]:
                    state = str(record.get("status") or "unknown").capitalize()
                    if str(record.get("id")) in superseded_activity_ids:
                        state = "Superseded"
                    state_color = "#16834a" if state == "Succeeded" else "#c0393b" if state == "Failed" else "#777"
                    st.markdown(
                        f"<span style='color:{state_color};font-weight:650'>{html.escape(state)}</span>",
                        unsafe_allow_html=True,
                    )
                with columns[3]:
                    st.write(project_name)
                    st.caption(str(record.get("project_id") or project_id))
                with columns[4]:
                    if st.button(
                        "View details", key=f"view_generation_activity_{record['id']}",
                        width="stretch",
                    ):
                        _show_generation_activity_details(record)
