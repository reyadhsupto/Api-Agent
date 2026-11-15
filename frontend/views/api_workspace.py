# frontend/views/api_workspace.py

"""
API Workspace view: collections, request tabs, and the send/response playground.
"""

import streamlit as st

from frontend.styles import METHOD_COLORS, REQUEST_TAB_CSS

from frontend.core import (
    _new_request_draft,
    _render_collection_navigator,
    _render_contract_import_panel,
    _render_request_draft,
)


def render_api_workspace() -> None:
    """Render saved project collections, generation selection, and request tabs."""
    st.markdown(REQUEST_TAB_CSS, unsafe_allow_html=True)
    st.markdown(
        """<style>
        input[aria-label="URL"], textarea[aria-label="Body"] {
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        }
        div[data-baseweb="tab-list"] { gap: .35rem; }
        div[data-baseweb="tab"] { padding: .45rem .9rem; font-size: .92rem; }
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { font-weight: 650; }
        div[data-testid="stDataEditor"] { border-radius: .5rem; }
        .st-key-request-playground-sticky {
            position: sticky; top: .5rem; align-self: flex-start; z-index: 3;
        }

        /* Keep the navigator and playground side by side until the page is narrow. */
        .st-key-api-workspace-layout {
            --aa-panel-bg: color-mix(in srgb, var(--st-secondary-background-color) 72%, transparent);
            --aa-panel-border: color-mix(in srgb, var(--st-border-color) 82%, transparent);
        }
        .st-key-api-workspace-layout [data-testid="stHorizontalBlock"]:has(.st-key-collection-browser-header),
        .st-key-api-workspace-layout > [data-testid="stHorizontalBlock"],
        .st-key-api-workspace-layout > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
            display: grid !important;
            grid-template-columns: clamp(270px, 17vw, 320px) minmax(0, 1fr) !important;
            align-items: start; gap: 1rem !important;
        }
        .st-key-api-workspace-layout [data-testid="stHorizontalBlock"]:has(.st-key-collection-browser-header) > :is([data-testid="column"], [data-testid="stColumn"]),
        .st-key-api-workspace-layout > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]),
        .st-key-api-workspace-layout > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > :is([data-testid="column"], [data-testid="stColumn"]) {
            width: auto !important; min-width: 0 !important; flex: initial !important;
        }

        /* One shared panel surface frames the project heading, search, and tree. */
        .st-key-collection-browser-header {
            box-sizing: border-box; width: 100%; max-width: 100%;
            padding: .7rem .65rem .55rem;
            border: 1px solid var(--aa-panel-border);
            border-radius: 12px 12px 0 0;
            background: var(--aa-panel-bg);
        }
        .aa-navigator-title {
            overflow: hidden; font-size: 1.02rem; font-weight: 720;
            letter-spacing: -.025em; text-overflow: ellipsis; white-space: nowrap;
        }
        .aa-navigator-subtitle {
            margin-top: .12rem; font-size: .68rem; font-weight: 600;
            letter-spacing: .075em; text-transform: uppercase; opacity: .62;
        }
        .st-key-collection-browser-header [data-testid="stButton"] button {
            min-height: 2rem; padding-inline: .3rem; border-radius: 7px !important;
            font-size: .76rem; font-weight: 650;
        }
        .st-key-navigator-search-row {
            box-sizing: border-box; width: 100%; max-width: 100%;
            padding: .45rem .65rem;
            border-left: 1px solid var(--aa-panel-border);
            border-right: 1px solid var(--aa-panel-border);
            background: var(--aa-panel-bg);
        }
        .st-key-navigator-search-row [data-testid="stHorizontalBlock"] {
            align-items: center; gap: .35rem;
        }
        .st-key-navigator-search-row :is([data-testid="column"], [data-testid="stColumn"]) { min-width: 0; padding: 0; }
        .st-key-navigator-search-row :is([data-testid="column"], [data-testid="stColumn"]):first-child {
            flex: 0 0 2.25rem !important; width: 2.25rem !important;
        }
        .st-key-navigator-search-row [data-testid="stTextInput"] input {
            min-height: 2.25rem; border-radius: 8px !important; font-size: .8rem;
        }

        /* Method filter row and enabled counter, aligned with the panel frame. */
        .st-key-navigator-filter-row {
            box-sizing: border-box; width: 100%; max-width: 100%;
            padding: .05rem .65rem .4rem;
            border-left: 1px solid var(--aa-panel-border);
            border-right: 1px solid var(--aa-panel-border);
            background: var(--aa-panel-bg);
        }
        .st-key-navigator-filter-row [data-testid="stButtonGroup"] { gap: .15rem; flex-wrap: nowrap; }
        .st-key-navigator-filter-row button {
            min-height: 1.8rem; padding-inline: .55rem;
            font-size: .72rem; font-weight: 620; border-radius: 999px !important;
        }
        .aa-nav-counter { font-size: .68rem; opacity: .62; margin: .1rem 0 .3rem; }
        div[class*="st-key-collection-tree-row-partial-"] [data-testid="stCheckbox"] { opacity: .72; }

        /* Compact tree rows keep eligibility at the left and actions at the right. */
        .st-key-collection-browser-scroll {
            box-sizing: border-box; width: 100%; max-width: 100%;
            max-height: min(70vh, 760px); overflow-x: hidden; overflow-y: auto; overscroll-behavior: contain;
            padding: .45rem .65rem .65rem;
            border: 1px solid var(--aa-panel-border); border-top: 0;
            border-radius: 0 0 12px 12px; background: var(--aa-panel-bg);
            scrollbar-gutter: stable;
        }
        .st-key-collection-browser-header > [data-testid="stVerticalBlock"],
        .st-key-navigator-search-row > [data-testid="stVerticalBlock"],
        .st-key-collection-browser-scroll > [data-testid="stVerticalBlock"] {
            box-sizing: border-box; width: 100%; max-width: 100%; min-width: 0;
        }
        .st-key-collection-browser-scroll > [data-testid="stVerticalBlock"] { gap: .1rem; }
        .st-key-collection-browser-scroll::-webkit-scrollbar { width: 7px; }
        .st-key-collection-browser-scroll::-webkit-scrollbar-thumb {
            border-radius: 20px; background: rgba(128,128,128,.28);
        }
        div[class*="st-key-collection-tree-row-"] {
            box-sizing: border-box; width: 100%; max-width: 100%; min-width: 0;
            margin: 2px 0; padding: 2px 3px;
            border: 1px solid transparent; border-radius: 8px;
            transition: background .14s ease, border-color .14s ease;
        }
        div[class*="st-key-collection-tree-row-expanded-"] { position: relative; }
        div[class*="st-key-collection-tree-row-expanded-"]::after {
            content: ""; position: absolute; z-index: 0; left: 1.25rem;
            bottom: -.55rem; height: .55rem; border-left: 1px solid var(--aa-border);
            pointer-events: none;
        }
        div[class*="st-key-collection-tree-row-"]:hover,
        div[class*="st-key-browser-request-row-"]:hover,
        div[class*="st-key-browser-request-row-"]:focus-within {
            background: var(--aa-surface-hover); border-color: var(--aa-border);
        }
        div[class*="st-key-collection-tree-row-selected-"] {
            background: var(--aa-accent-soft); border-color: rgba(255,108,55,.22);
        }
        div[class*="st-key-collection-tree-row-"] [data-testid="stHorizontalBlock"],
        div[class*="st-key-browser-request-row-"] [data-testid="stHorizontalBlock"] {
            box-sizing: border-box; width: 100%; max-width: 100%; min-width: 0;
            align-items: center; gap: .25rem;
        }
        div[class*="st-key-collection-tree-row-"] :is([data-testid="column"], [data-testid="stColumn"]),
        div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]) {
            box-sizing: border-box; min-width: 0; padding: 0;
        }
        div[class*="st-key-collection-tree-row-"] :is([data-testid="column"], [data-testid="stColumn"]) > [data-testid="stVerticalBlock"],
        div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]) > [data-testid="stVerticalBlock"] {
            min-width: 0; min-height: 2.2rem; justify-content: center; gap: 0;
        }
        div[class*="st-key-collection-tree-row-"] :is([data-testid="column"], [data-testid="stColumn"]):first-child {
            flex: 0 0 1.3rem !important; width: 1.3rem !important;
        }
        div[class*="st-key-collection-tree-row-"] :is([data-testid="column"], [data-testid="stColumn"]):last-child {
            flex: 0 0 2rem !important; width: 2rem !important;
        }
        div[class*="st-key-collection-tree-row-"] [data-testid="stButton"] button {
            min-height: 2.25rem; justify-content: flex-start !important;
            padding-inline: .35rem; border-radius: 7px !important;
            font-size: .82rem; font-weight: 620; text-align: left;
        }
        div[class*="st-key-collection-tree-row-"] [data-testid="stButton"] button p {
            overflow: hidden; text-align: left; text-overflow: ellipsis; white-space: nowrap;
        }
        div[class*="st-key-browser-request-row-"] {
            box-sizing: border-box; width: 100%; max-width: 100%; min-width: 0;
            margin: 2px 0; padding: 2px 3px;
            border: 1px solid transparent; border-radius: 8px;
            position: relative;
            transition: background .14s ease, border-color .14s ease;
        }
        div[class*="st-key-browser-request-row-"]::before {
            content: ""; position: absolute; z-index: 0; left: 1.55rem;
            top: -.2rem; bottom: -.2rem; border-left: 1px solid var(--aa-border);
            pointer-events: none;
        }
        div[class*="st-key-browser-request-row-"]::after {
            content: ""; position: absolute; z-index: 0; left: 1.55rem;
            top: 50%; width: .45rem; border-top: 1px solid var(--aa-border);
            pointer-events: none;
        }
        div[class*="st-key-browser-request-row-selected-"] {
            background: var(--aa-accent-soft); border-color: rgba(255,108,55,.22);
        }
        div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]):nth-child(1) {
            flex: 0 0 1.3rem !important; width: 1.3rem !important;
        }
        div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]):nth-child(2) {
            flex: 0 0 3.8rem !important; width: 3.8rem !important;
        }
        div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]):nth-child(3) {
            flex: 1 1 0% !important; width: 0 !important;
        }
        div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]):last-child {
            flex: 0 0 2rem !important; width: 2rem !important;
        }
        div[class*="st-key-collection-tree-row-"] [data-testid="stCheckbox"],
        div[class*="st-key-browser-request-row-"] [data-testid="stCheckbox"] {
            display: flex; justify-content: center; margin: 0;
        }
        div[class*="st-key-collection-tree-row-"] [data-testid="stCheckbox"] label,
        div[class*="st-key-browser-request-row-"] [data-testid="stCheckbox"] label {
            padding: 0; gap: 0; justify-content: center;
        }
        div[class*="st-key-browser-request-row-"] [data-testid="stButton"] button {
            box-sizing: border-box; min-height: 2.2rem; width: 100%; justify-content: flex-start !important;
            align-items: center !important; line-height: 1.2;
            padding-inline: .35rem; border-radius: 6px !important; text-align: left;
        }
        div[class*="st-key-browser-request-row-"] [data-testid="stButton"] button > div {
            width: 100%; justify-content: flex-start !important;
        }
        div[class*="st-key-browser-request-row-"] [data-testid="stButton"] button p {
            max-width: 100%; margin: 0; overflow: hidden; text-align: left;
            text-overflow: ellipsis; white-space: nowrap;
        }
        div[class*="st-key-browser-request-row-"] [data-testid="stMarkdown"],
        div[class*="st-key-browser-request-row-"] [data-testid="stMarkdown"] p {
            margin: 0; line-height: 1.2;
        }
        div[class*="st-key-close_contract_import_"] button,
        div[class*="st-key-close_contract_discovery_"] button {
            width: 2rem; min-width: 2rem; height: 2rem; min-height: 2rem;
            padding: 0; border-radius: 7px !important;
        }
        div[class*="st-key-close_contract_import_"] button p,
        div[class*="st-key-close_contract_discovery_"] button p {
            position: absolute !important; width: 1px !important; height: 1px !important;
            margin: -1px !important; padding: 0 !important; overflow: hidden !important;
            clip: rect(0, 0, 0, 0) !important; white-space: nowrap !important; border: 0 !important;
        }
        /* Keep the navigator kebab triggers as plain, unboxed three-dot icons. */
        .st-key-navigator-search-row [data-testid="stPopover"] button,
        div[class*="st-key-collection-tree-row-"] [data-testid="stPopover"] button,
        div[class*="st-key-browser-request-row-"] [data-testid="stPopover"] button {
            display: inline-flex; box-sizing: border-box; width: 1.75rem; min-width: 1.75rem;
            height: 2rem; min-height: 2rem; align-items: center; justify-content: center;
            padding: 0 !important; border: 0 !important; border-radius: 0 !important;
            background: transparent !important; box-shadow: none !important;
            color: inherit; opacity: .40; appearance: none;
            transition: opacity .14s ease, color .14s ease;
        }
        .st-key-navigator-search-row [data-testid="stPopover"] button p,
        div[class*="st-key-collection-tree-row-"] [data-testid="stPopover"] button p,
        div[class*="st-key-browser-request-row-"] [data-testid="stPopover"] button p {
            position: absolute !important; width: 1px !important; height: 1px !important;
            margin: -1px !important; padding: 0 !important; overflow: hidden !important;
            clip: rect(0, 0, 0, 0) !important; white-space: nowrap !important; border: 0 !important;
        }
        .st-key-navigator-search-row [data-testid="stPopover"] button:hover,
        div[class*="st-key-collection-tree-row-"]:hover [data-testid="stPopover"] button,
        div[class*="st-key-browser-request-row-"]:hover [data-testid="stPopover"] button,
        .st-key-navigator-search-row [data-testid="stPopover"] button:focus-visible,
        div[class*="st-key-collection-tree-row-"] [data-testid="stPopover"] button:focus-visible,
        div[class*="st-key-browser-request-row-"] [data-testid="stPopover"] button:focus-visible {
            opacity: 1; color: var(--aa-accent) !important;
            background: transparent !important; border: 0 !important; box-shadow: none !important;
        }
        .st-key-navigator-search-row [data-testid="stPopover"] button:focus-visible,
        div[class*="st-key-collection-tree-row-"] [data-testid="stPopover"] button:focus-visible,
        div[class*="st-key-browser-request-row-"] [data-testid="stPopover"] button:focus-visible {
            outline: 2px solid var(--aa-accent); outline-offset: 1px;
        }
        div[class*="st-key-browser-request-row-"] [data-testid="stPopoverBody"] { min-width: 225px; }

        .st-key-contract-import-panel [data-testid="stDataEditor"] { max-height: 185px; }
        .st-key-contract-candidate-list {
            max-height: 220px; overflow-y: auto; overscroll-behavior: contain;
            padding: .35rem .55rem; border: 1px solid var(--aa-border);
            border-radius: var(--aa-radius-sm); background: var(--aa-surface);
        }
        @media (max-width: 760px) {
            .st-key-collection-browser-scroll { max-height: 46vh; }
            .st-key-api-workspace-layout [data-testid="stHorizontalBlock"]:has(.st-key-collection-browser-header),
            .st-key-api-workspace-layout > [data-testid="stHorizontalBlock"],
            .st-key-api-workspace-layout > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
                grid-template-columns: minmax(0, 1fr) !important;
            }
            .st-key-request-playground-sticky { position: static; }
        }
        @media (prefers-reduced-motion: reduce) {
            div[class*="st-key-collection-tree-row-"],
            div[class*="st-key-browser-request-row-"] { transition: none; }
        }
        </style>""",
        unsafe_allow_html=True,
    )
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
