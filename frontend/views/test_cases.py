# frontend/views/test_cases.py

"""
Test Cases view: generation panel, test-case list, and execution results.
"""

import streamlit as st

from frontend.styles import TEST_CASES_TOPBAR_CSS, TEST_CASE_CSS

from frontend.core import (
    _deduplicate_test_cases,
    _render_manual_case_builder,
    _render_test_run_manager,
    _test_case_sort_key,
    render_generation_panel,
    render_test_case_list,
)


def render_test_cases_tab() -> None:
    """Render generation controls and execution results in one workspace.

    Returns:
        None: Writes the Test Cases page to the Streamlit app.
    """
    st.markdown(TEST_CASE_CSS, unsafe_allow_html=True)
    st.markdown(TEST_CASES_TOPBAR_CSS, unsafe_allow_html=True)
    with st.container(key="test-cases-workspace"):
        raw_test_cases = st.session_state.get("test_cases", [])
        deduplicated_cases = _deduplicate_test_cases(raw_test_cases)
        if not isinstance(raw_test_cases, (list, tuple)) or len(deduplicated_cases) != len(raw_test_cases):
            st.session_state["test_cases"] = deduplicated_cases
            st.warning("Malformed test-case entries were ignored, and duplicate IDs were collapsed to the latest copy.")
        test_cases = [case for case in deduplicated_cases if not case.get("superseded_by_activity_id")]
        project = st.session_state.get("current_project") or {}
        test_cases.sort(key=_test_case_sort_key)
        with st.container(key="test-cases-topbar"):
            title_col, add_col, runs_col = st.columns(
                [6, 1.5, 1.6], vertical_alignment="center",
            )
            with title_col:
                st.markdown("### Test Cases")
                st.caption("Generate, review, and run test cases across your saved requests.")
            with add_col:
                with st.container(key="add-manual-test-action"):
                    _render_manual_case_builder(project)
            with runs_col:
                with st.container(key="reusable-runs-action"):
                    loaded_run_id = _render_test_run_manager(project, test_cases)
        render_generation_panel()
        render_test_case_list(loaded_run_id)
