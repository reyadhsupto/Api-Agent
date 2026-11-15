# frontend/styles/__init__.py

"""
Style package for the Api-Agent frontend.

Design tokens live in ``tokens``. Every surface owns a small module holding its
own CSS string, so the entry point never carries raw markup. ``inject_styles``
emits the theme variables and the global stylesheet in a single call.

Accepts:
    theme (str | None): Optional palette override. ``None`` uses ``DEFAULT_THEME``.

Returns:
    None: Styles are written to the Streamlit page as a side effect.
"""

import streamlit as st

from frontend.styles.base import GLOBAL_CSS
from frontend.styles.request_tabs import REQUEST_TAB_CSS
from frontend.styles.shell import SHELL_CSS
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
    "LIGHT",
    "METHOD_COLORS",
    "MOTION",
    "PALETTES",
    "RADII",
    "REQUEST_TAB_CSS",
    "SHELL_CSS",
    "TEST_CASES_TOPBAR_CSS",
    "TEST_CASE_CSS",
    "active_theme",
    "css_variables",
    "inject_styles",
    "palette",
]


def active_theme() -> str:
    """Return the palette name for the current session.

    Returns:
        str: Always ``DEFAULT_THEME`` (light) for now. The dark palette ships
        with the tokens but is not wired to a control, because Streamlit
        cannot retheme its own widgets at runtime.
    """
    return DEFAULT_THEME


def inject_styles(theme: str | None = None) -> None:
    """Emit the design tokens plus every stylesheet the app needs.

    Args:
        theme (str | None): Palette override; ``None`` uses the active theme.

    Returns:
        None: Writes one ``<style>`` block to the Streamlit page.
    """
    chosen = theme or active_theme()
    st.markdown(
        "<style>" + css_variables(chosen) + "</style>"
        + GLOBAL_CSS + SHELL_CSS,
        unsafe_allow_html=True,
    )
