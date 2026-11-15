# frontend/app.py

"""
Streamlit entry point for Api-Agent.

Running this file with ``streamlit run frontend/app.py`` renders the shell and
the four workspace tabs. Shared state, API clients, CSS constants, and render
helpers live in ``frontend/core.py``; each tab is a module under
``frontend/views``.

The repository root is added to sys.path so the absolute ``frontend.*`` imports
below resolve both when Streamlit executes this file as a script and when the
test-suite imports it as ``frontend.app``.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st  # noqa: E402

from frontend.core import (  # noqa: E402
    _flush_toasts,
    _hero,
    _queue_toast,
    api_delete,
    api_get,
    api_post,
    initialize_session_state,
    load_project,
    refresh_project_list,
)

import frontend.core as _core  # noqa: E402
from frontend.styles import inject_styles  # noqa: E402


# The frontend used to live in this module. Mirror the shared core namespace,
# private names included, so older imports such as
# ``from frontend.app import _deduplicate_test_cases`` keep resolving.
globals().update({
    name: value for name, value in vars(_core).items() if not name.startswith("__")
})

from frontend.views.activity import render_generation_activity_tab  # noqa: E402
from frontend.views.api_workspace import render_api_workspace  # noqa: E402
from frontend.views.chat import render_project_chat_tab  # noqa: E402
from frontend.views.test_cases import render_test_cases_tab  # noqa: E402


def main() -> None:
    """Main Streamlit application entry point."""
    st.set_page_config(
        page_title="Api-Agent",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    initialize_session_state()
    _flush_toasts()
    inject_styles()
    modes = ("API Workspace", "Test Cases", "Project Chat", "Generation Activity")
    st.sidebar.markdown(
        "<div class='aa-rail-brand'><span class='aa-rail-mark'>AA</span>"
        "<span class='aa-rail-name'>Api-Agent</span></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.radio("Workspace mode", modes, key="ui_mode", label_visibility="collapsed")
    st.sidebar.divider()
    current_project = st.session_state.get("current_project") or {}
    _hero("Api-Agent", "Compose API requests, generate test cases, and inspect execution results.")
    if current_project:
        st.caption(
            f"Project: **{current_project.get('name', 'Untitled')}** · "
            f"{len(current_project.get('collections', []))} collections · "
            f"{len(current_project.get('endpoints', []))} saved requests · "
            f"{len(current_project.get('test_cases', []))} test cases"
        )

    with st.sidebar:
        _hero("Workspace", "Project and saved test data", mark="AA")
        refresh_project_list()
        project_list = st.session_state.get("project_list", [])
        project_by_id = {project["id"]: project for project in project_list}
        short_ids = [project_id[:8] for project_id in project_by_id]
        project_labels = {
            project_id: f"{project['name']} · {project_id[:8] if short_ids.count(project_id[:8]) == 1 else project_id}"
            for project_id, project in project_by_id.items()
        }
        if st.session_state.get("persisted_project_id") is None:
            try:
                st.session_state["persisted_project_id"] = api_get("/api/v1/memory/state").get("current_project_id")
            except Exception:
                st.session_state["persisted_project_id"] = None
        current_project = st.session_state.get("current_project") or {}
        current_id = current_project.get("id") or st.session_state.get("persisted_project_id")
        if current_id not in project_by_id and project_list:
            current_id = project_list[0]["id"]
        if project_list:
            selected_pid = st.selectbox(
                "Project",
                options=list(project_by_id),
                index=list(project_by_id).index(current_id),
                format_func=lambda project_id: project_labels[project_id],
                key="project_selector_" + "_".join(sorted(project_by_id)),
            )
            if current_project.get("id") != selected_pid:
                load_project(selected_pid)
                st.rerun()
            st.session_state["persisted_project_id"] = selected_pid
        else:
            selected_pid = None
            st.info("No projects available.")

        with st.expander("Project actions", expanded=False):
            with st.form("create_project_form", clear_on_submit=True):
                new_project_name = st.text_input("Project name", placeholder="Enter project name")
                new_project_desc = st.text_input("Description", placeholder="Optional description")
                create_project_clicked = st.form_submit_button("Create project", type="primary")
            if create_project_clicked:
                if new_project_name.strip():
                    project = api_post("/api/v1/projects", {
                        "name": new_project_name.strip(),
                        "description": new_project_desc.strip(),
                    })
                    st.session_state["current_project"] = None
                    refresh_project_list(force=True)
                    load_project(project["id"])
                    _queue_toast("Project created.")
                    st.rerun()
                else:
                    st.error("Project name is required")
            if selected_pid and st.button("Delete selected project", type="secondary"):
                api_delete(f"/api/v1/projects/{selected_pid}")
                st.session_state["current_project"] = None
                st.session_state["endpoints"] = []
                st.session_state["request_drafts"] = []
                st.session_state["test_cases"] = []
                st.session_state["executions"] = {}
                st.session_state["persisted_project_id"] = None
                refresh_project_list(force=True)
                _queue_toast("Project deleted.")
                st.rerun()

        current_project = st.session_state.get("current_project")
        if current_project:
            st.markdown(
                "<div class='aa-stats'>"
                f"<div><span>{len(current_project.get('collections', []))}</span><label>Collections</label></div>"
                f"<div><span>{len(current_project.get('endpoints', []))}</span><label>Requests</label></div>"
                f"<div><span>{len(current_project.get('test_cases', []))}</span><label>Tests</label></div>"
                "</div>",
                unsafe_allow_html=True,
            )

            if st.button("Fetch saved test cases", type="secondary", icon=":material/refresh:", use_container_width=True):
                tcs = api_get(f"/api/v1/projects/{current_project['id']}/test-cases")
                st.session_state["test_cases"] = tcs
                st.session_state["executions"] = {}
                _queue_toast(f"Fetched {len(tcs)} test case(s).")
                st.rerun()

    mode = st.session_state.get("ui_mode") or modes[0]

    if mode == "API Workspace":
        render_api_workspace()

    current_project = st.session_state.get("current_project") or {}
    all_saved_requests = current_project.get("endpoints", [])
    generation_eligible = [
        item for item in all_saved_requests
        if item.get("include_for_generation", item.get("include", False))
    ]
    generation_by_id = {item["id"]: item for item in generation_eligible}
    ordered_ids = [
        item for item in st.session_state.get("generation_order_ids", [])
        if item in generation_by_id
    ]
    ordered_ids.extend(item["id"] for item in generation_eligible if item["id"] not in ordered_ids)
    st.session_state["generation_order_ids"] = ordered_ids
    st.session_state["endpoints"] = [generation_by_id[item] for item in ordered_ids]
    st.session_state["parsed_curl"] = st.session_state["endpoints"][0] if st.session_state["endpoints"] else None

    if mode == "Test Cases":
        render_test_cases_tab()
    elif mode == "Project Chat":
        render_project_chat_tab()
    elif mode == "Generation Activity":
        render_generation_activity_tab()

    _flush_toasts()

if __name__ == "__main__":
    main()

