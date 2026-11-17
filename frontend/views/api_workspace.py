# frontend/views/api_workspace.py

"""
API Workspace view: collections, request tabs, and the send/response playground.
"""

import streamlit as st

from frontend.styles import METHOD_COLORS, REQUEST_TAB_CSS
from frontend.styles.layout import LAYOUT_CSS

from frontend.core import (
    _new_request_draft,
    _render_collection_navigator,
    _render_contract_import_panel,
    _render_request_draft,
)


def render_api_workspace() -> None:
    """Render saved project collections, generation selection, and request tabs."""
    st.markdown(REQUEST_TAB_CSS, unsafe_allow_html=True)
    st.markdown(LAYOUT_CSS, unsafe_allow_html=True)

    project = st.session_state.get("current_project") or {}
    collections = project.get("collections", [])
    project_id = project.get("id")
    if not project_id:
        st.header("API Workspace")
        st.warning("Select or create a project to manage request collections.")
        return

    with st.container(key="api-workspace-layout"):
        left, editor = st.columns([1, 5], gap="small")
        with left:
            selected_id = _render_collection_navigator(project, project_id)

        with editor:
            active_contract_panel = st.session_state.get("workspace_contract_panel")
            if active_contract_panel == "import":
                st.markdown("<style>.st-key-contract-discovery-expander { display: none !important; }</style>", unsafe_allow_html=True)
            elif active_contract_panel == "discover":
                st.markdown("<style>.st-key-contract-import-expander { display: none !important; }</style>", unsafe_allow_html=True)
            with st.container(key="contract-import-panel"):
                _render_contract_import_panel(project_id, project.get("collections", []))

        with editor, st.container(key="request-playground-sticky"):
            drafts = st.session_state["request_drafts"]
            if not drafts:
                st.info("Start by creating a request, or open one from Saved requests.")
                if st.button("New Request", type="primary", key="new_request_tab_empty"):
                    draft = _new_request_draft()
                    draft["collection_id"] = selected_id
                    st.session_state["request_drafts"].append(draft)
                    st.session_state["active_request_tab_id"] = draft["tab_id"]
                    st.rerun()
            else:
                active_id = st.session_state.get("active_request_tab_id")
                if active_id not in {draft["tab_id"] for draft in drafts}:
                    active_id = drafts[0]["tab_id"]
                    st.session_state["active_request_tab_id"] = active_id

                with st.container(horizontal=True, key="request-tabbar", wrap=False):
                    for index, draft in enumerate(drafts):
                        request_name = draft.get("name") or "New Request"
                        method_label = draft.get("method", "GET").upper()
                        full_label = f"{method_label} {request_name}"
                        if draft.get("dirty"):
                            full_label = "Unsaved changes - " + full_label
                        tab_label = request_name if len(request_name) <= 22 else f"{request_name[:19]}…"
                        if draft.get("dirty"):
                            tab_label = "* " + tab_label
                        method_color = METHOD_COLORS.get(method_label, "gray")
                        is_active = draft["tab_id"] == active_id
                        with st.container(
                            horizontal=True,
                            key=f"request-tab-{'on' if is_active else 'off'}-{draft['tab_id']}",
                        ):
                            if st.button(
                                f":{method_color}[**{method_label}**]  {tab_label}",
                                key=f"select_request_tab_{draft['tab_id']}",
                                type="tertiary",
                                help=f"Switch to {full_label}",
                                width="stretch",
                            ):
                                st.session_state["active_request_tab_id"] = draft["tab_id"]
                                st.rerun()
                            with st.container(key=f"request-close-{draft['tab_id']}"):
                                if st.button(
                                    "×", key=f"close_request_tab_{draft['tab_id']}",
                                    type="tertiary", help="Close request",
                                ):
                                    st.session_state["request_drafts"] = [
                                        item for item in drafts if item["tab_id"] != draft["tab_id"]
                                    ]
                                    if is_active:
                                        remaining = st.session_state["request_drafts"]
                                        previous_index = max(index - 1, 0)
                                        st.session_state["active_request_tab_id"] = (
                                            remaining[previous_index]["tab_id"] if remaining else None
                                        )
                                    st.rerun()
                    with st.container(key="request-add"):
                        if st.button("+", key="new_request_tab_plus", type="tertiary", help="Add request"):
                            draft = _new_request_draft()
                            draft["collection_id"] = selected_id
                            st.session_state["request_drafts"].append(draft)
                            st.session_state["active_request_tab_id"] = draft["tab_id"]
                            st.rerun()

                active_draft = next(draft for draft in drafts if draft["tab_id"] == active_id)
                st.caption("Request tabs are temporary drafts. Save a request to keep it in a collection.")
                _render_request_draft(active_draft, collections, project_id)
