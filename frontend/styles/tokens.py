# frontend/styles/tokens.py

"""
Design tokens for the Api-Agent frontend.

The palette follows a Postman-like dark workspace on a pure black canvas, with the
signature orange accent, dense rows, and monospace detail text. Tokens are
emitted as CSS custom properties so every style module stays declarative. A light
palette is kept for a future theme switch.

Accepts:
    theme (str): Either "dark" or "light".

Returns:
    str: A ``:root`` rule declaring every token for the requested theme.
"""

METHOD_COLORS = {
    "GET": "green",
    "POST": "orange",
    "PUT": "blue",
    "PATCH": "violet",
    "DELETE": "red",
    "HEAD": "gray",
    "OPTIONS": "gray",
    "TRACE": "gray",
}

RADII = {
    "aa-radius-xs": "6px",
    "aa-radius-sm": "8px",
    "aa-radius": "12px",
    "aa-radius-lg": "16px",
}

MOTION = {
    "aa-fast": "120ms",
    "aa-base": "180ms",
    "aa-slow": "260ms",
    "aa-ease": "cubic-bezier(.2,.8,.2,1)",
}

FONTS = {
    "aa-font-ui": (
        "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', "
        "Inter, Roboto, Helvetica, Arial, sans-serif"
    ),
    "aa-font-mono": (
        "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
    ),
}

DARK = {
    "aa-accent": "#ff6c37",
    "aa-accent-hover": "#ff8355",
    "aa-accent-press": "#e2521f",
    "aa-accent-rgb": "255, 108, 55",
    "aa-accent-soft": "rgba(255, 108, 55, .16)",
    "aa-fg-rgb": "255, 255, 255",
    "aa-ok": "#2ea043",
    "aa-ok-strong": "#238636",
    "aa-warn": "#d29922",
    "aa-bad": "#f85149",
    "aa-bad-strong": "#da3633",
    "aa-info": "#58a6ff",
    "aa-canvas": "#000000",
    "aa-rail": "#050506",
    "aa-panel": "#0a0a0c",
    "aa-elevated": "#101013",
    "aa-hover": "#16161a",
    "aa-active": "#1e1e24",
    "aa-border": "rgba(255, 255, 255, .09)",
    "aa-border-strong": "rgba(255, 255, 255, .18)",
    "aa-surface": "rgba(255, 255, 255, .04)",
    "aa-surface-hover": "rgba(255, 255, 255, .075)",
    "aa-text": "#f2f3f5",
    "aa-text-dim": "#a3a9b4",
    "aa-text-mute": "#6d737d",
    "aa-code-bg": "#000000",
    "aa-code-border": "rgba(255, 255, 255, .10)",
    "aa-shadow-1": "0 1px 2px rgba(0, 0, 0, .85)",
    "aa-shadow-2": "0 8px 22px rgba(0, 0, 0, .90)",
    "aa-shadow-3": "0 20px 48px rgba(0, 0, 0, .95)",
    "background-color": "#000000",
    "secondary-background-color": "#0a0a0c",
    "text-color": "#f2f3f5",
    "secondary-text-color": "#a3a9b4",
    "border-color": "rgba(255, 255, 255, .09)",
    "primary-color": "#ff6c37",
    "code-background-color": "#000000",
    "st-background-color": "#000000",
    "st-secondary-background-color": "#0a0a0c",
    "st-text-color": "#f2f3f5",
    "st-secondary-text-color": "#a3a9b4",
    "st-border-color": "rgba(255, 255, 255, .09)",
    "st-primary-color": "#ff6c37",
    "st-code-background-color": "#000000",
}

LIGHT = {
    "aa-accent": "#ff6c37",
    "aa-accent-hover": "#f25c26",
    "aa-accent-press": "#dd4f1c",
    "aa-accent-rgb": "255, 108, 55",
    "aa-accent-soft": "rgba(255, 108, 55, .12)",
    "aa-fg-rgb": "15, 23, 42",
    "aa-ok": "#2e9e5b",
    "aa-ok-strong": "#247c47",
    "aa-warn": "#b7791f",
    "aa-bad": "#e5484d",
    "aa-bad-strong": "#bd3439",
    "aa-info": "#3269a8",
    "aa-canvas": "#f7f8fa",
    "aa-rail": "#ffffff",
    "aa-panel": "#ffffff",
    "aa-elevated": "#ffffff",
    "aa-hover": "#eef0f4",
    "aa-active": "#e6e9ef",
    "aa-border": "rgba(15, 23, 42, .10)",
    "aa-border-strong": "rgba(15, 23, 42, .18)",
    "aa-surface": "rgba(15, 23, 42, .035)",
    "aa-surface-hover": "rgba(15, 23, 42, .07)",
    "aa-text": "#16181d",
    "aa-text-dim": "#566070",
    "aa-text-mute": "#8a929e",
    "aa-code-bg": "#f3f4f7",
    "aa-code-border": "rgba(15, 23, 42, .08)",
    "aa-shadow-1": "0 1px 2px rgba(15, 23, 42, .08)",
    "aa-shadow-2": "0 6px 18px rgba(15, 23, 42, .10)",
    "aa-shadow-3": "0 16px 40px rgba(15, 23, 42, .14)",
    "background-color": "#f7f8fa",
    "secondary-background-color": "#ffffff",
    "text-color": "#16181d",
    "primary-color": "#ff6c37",
    "secondary-text-color": "#566070",
    "border-color": "rgba(15, 23, 42, .10)",
    "code-background-color": "#f3f4f7",
    "st-background-color": "#f7f8fa",
    "st-secondary-background-color": "#ffffff",
    "st-text-color": "#16181d",
    "st-secondary-text-color": "#566070",
    "st-border-color": "rgba(15, 23, 42, .10)",
    "st-primary-color": "#ff6c37",
    "st-code-background-color": "#f3f4f7",
}

PALETTES = {"dark": DARK, "light": LIGHT}
DEFAULT_THEME = "dark"


def palette(theme: str = DEFAULT_THEME) -> dict[str, str]:
    """Return the token map for a theme name.

    Args:
        theme (str): Requested theme; unknown values fall back to dark.

    Returns:
        dict[str, str]: Token name to CSS value mapping.
    """
    return PALETTES.get(str(theme).lower(), DARK)


def css_variables(theme: str = DEFAULT_THEME) -> str:
    """Render the design tokens as a CSS custom property block.

    Args:
        theme (str): Requested theme; unknown values fall back to dark.

    Returns:
        str: A ``:root`` rule declaring every token and radius/speed value.
    """
    tokens = {
        **palette(theme),
        **RADII,
        **MOTION,
        **FONTS,
    }
    lines = [":root {", "    color-scheme: " + theme + ";"]
    for name, value in tokens.items():
        lines.append("    --" + name + ": " + value + ";")
    lines.append("}")
    return "\n".join(lines)
