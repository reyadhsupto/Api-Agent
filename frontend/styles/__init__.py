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
    light          repaint of native chrome for the single light theme

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
    """Return the single supported palette name.

    Returns:
        str: The light palette name.
    """
    return DEFAULT_THEME


def inject_styles() -> None:
    """Emit the design tokens plus every stylesheet the app needs.

    Returns:
        None: Writes one ``<style>`` block to the Streamlit page.
    """
    chosen = DEFAULT_THEME
    st.markdown(
        "<style>" + css_variables(chosen) + "</style>"
        + GLOBAL_CSS + SHELL_CSS + SURFACES_CSS + LAYOUT_CSS + RAIL_CSS
        + REQUEST_TAB_CSS + TEST_CASE_CSS + TEST_CASES_TOPBAR_CSS
        + THEME_CSS
        + LIGHT_CSS,
        unsafe_allow_html=True,
    )
