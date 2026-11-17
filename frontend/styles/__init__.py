# frontend/styles/__init__.py

"""
Style package for the Api-Agent frontend.

Design tokens live in ``tokens``. Each visual layer owns a module holding one CSS
string, so the entry point never carries raw markup and no view re-defines a
surface:

    tokens         palette, radii, motion, fonts
    base           app padding and the branded header
    shell          canvas, rail, and sidebar chrome
    surfaces       card recipe plus the edges of native containers
    layout         workspace grid, collection rail, request tab strip
    rail           tree rows as visible boxes
    request_tabs   request tab strip
    test_cases     test case cards and toolbar
    theme          controls, menus, toasts, responsive rules
    light          repaint of native chrome while Light is active

``inject_styles`` emits exactly one ``<style>`` block per run.
"""

import streamlit as st

from frontend.styles.base import GLOBAL_CSS
from frontend.styles.light import LIGHT_CSS
from frontend.styles.layout import LAYOUT_CSS
from frontend.styles.rail import RAIL_CSS
from frontend.styles.request_tabs import REQUEST_TAB_CSS
from frontend.styles.shell import SHELL_CSS
from frontend.styles.surfaces import SURFACES_CSS
from frontend.styles.theme import THEME_CSS
from frontend.styles.test_cases import TEST_CASE_CSS, TEST_CASES_TOPBAR_CSS
from frontend.styles.tokens import (
    DEFAULT_THEME,
    FONTS,
    LIGHT,
    METHOD_COLORS,
    MOTION,
    PALETTES,
    RADII,
    css_variables,
    palette,
)

__all__ = [
    "DEFAULT_THEME",
    "FONTS",
    "GLOBAL_CSS",
    "LAYOUT_CSS",
    "LIGHT",
    "LIGHT_CSS",
    "METHOD_COLORS",
    "MOTION",
    "PALETTES",
    "RADII",
    "RAIL_CSS",
    "REQUEST_TAB_CSS",
    "SHELL_CSS",
    "SURFACES_CSS",
    "TEST_CASES_TOPBAR_CSS",
    "TEST_CASE_CSS",
    "THEME_CSS",
    "active_theme",
    "css_variables",
    "inject_styles",
    "palette",
]


def active_theme() -> str:
    """Return the palette name for the current session.

    The sidebar Appearance control is authoritative. ``st.context.theme.type``
    is only a fallback: Streamlit infers it from the background colour and
documents that it can lag behind a change in the settings menu, so trusting it
    over an explicit selection would flip the palette under the user.

    Returns:
        str: "light" when Light is selected, else ``DEFAULT_THEME``.
    """
    selected = str(st.session_state.get("ui_theme") or "").lower()
    if selected in {"light", "dark"}:
        return selected
    try:
        native = str(st.context.theme.type or "").lower()
    except Exception:
        return DEFAULT_THEME
    return native if native in {"light", "dark"} else DEFAULT_THEME


def inject_styles(theme: str | None = None) -> None:
    """Emit the design tokens plus every stylesheet the app needs.

    Args:
        theme (str | None): Palette override; ``None`` uses the active theme.

    Returns:
        None: Writes one ``<style>`` block to the Streamlit page.
    """
    chosen = str(theme or active_theme()).lower()
    if chosen not in PALETTES:
        chosen = DEFAULT_THEME
    st.markdown(
        "<style>" + css_variables(chosen) + "</style>"
        + GLOBAL_CSS + SHELL_CSS + SURFACES_CSS + LAYOUT_CSS + RAIL_CSS
        + REQUEST_TAB_CSS + TEST_CASE_CSS + TEST_CASES_TOPBAR_CSS
        + THEME_CSS
        + (LIGHT_CSS if chosen == "light" else ""),
        unsafe_allow_html=True,
    )
