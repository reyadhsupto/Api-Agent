# frontend/ui/theme_toggle.py

"""Sidebar appearance control for the light and dark palettes."""

import streamlit as st

THEME_OPTIONS = ("Dark", "Light")
THEME_KEY = "ui_theme"

HELP_TEXT = (
    "Dark is a pure black workspace. Light is a paper workspace. "
    "Streamlit paints widgets like the data grid and charts from its own "
    "theme at start-up, so those keep their dark canvas in Light mode; the "
    "frame around them follows the switch."
)


def render_theme_control() -> None:
    """Render the appearance switch in the sidebar.

    The chosen value persists in ``st.session_state`` so every rerun, including
    a project switch, keeps the selection. ``inject_styles`` reads the same key
    through ``frontend.styles.active_theme``.

    Returns:
        None: Writes the control to the sidebar.
    """
    st.sidebar.divider()
    st.sidebar.caption("Appearance")
    if st.session_state.get(THEME_KEY) not in THEME_OPTIONS:
        st.session_state[THEME_KEY] = THEME_OPTIONS[0]
    st.sidebar.segmented_control(
        "Theme",
        list(THEME_OPTIONS),
        key=THEME_KEY,
        label_visibility="collapsed",
        width="stretch",
        help=HELP_TEXT,
    )
