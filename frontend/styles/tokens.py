# frontend/styles/tokens.py

"""
Design tokens for the Api-Agent frontend.

Two palettes ship: a pure black ``dark`` workspace and a paper-on-grey ``light``
workspace. Both declare exactly the same token names, so every stylesheet is
written once against the semantic names and never branches on the theme.
``tests/test_theme_tokens.py`` asserts that parity, so a token added to one
palette cannot silently go missing from the other.

Token layers
    Surfaces   canvas, rail, panel, panel-alt, elevated, overlay
    Edges      line, line-soft, line-strong, line-contrast, line-accent
    Type       text, text-dim, text-mute, on-accent
    Meaning    accent, ok, warn, bad, info plus soft and strong variants
    Shape      box-fill, box-line, box-shadow, box-pad, chip-fill, chip-line

The ``line`` ladder exists because a border on pure black stops being visible
below roughly 1.4:1 contrast. ``line-soft`` is a divider inside a surface,
``line`` is the quiet card edge, ``line-strong`` is the hover edge, and
``line-contrast`` is reserved for interactive controls that must be
identifiable without hover (WCAG 1.4.11 asks for 3:1 there).

Accepts:
    theme (str): "dark" or "light".

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
    "aa-radius-md": "10px",
    "aa-radius": "12px",
    "aa-radius-lg": "16px",
    "aa-radius-pill": "999px",
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

# Ink for text sitting on the accent fill. White measures 2.8:1 on #ff6c37 and
# fails WCAG AA for the button sizes used here; this measures about 7.0:1.
ON_ACCENT = "#0b0d10"

DARK = {
    "aa-accent": "#ff6c37",
    "aa-accent-hover": "#ff8355",
    "aa-accent-press": "#e2521f",
    "aa-accent-rgb": "255, 108, 55",
    "aa-accent-soft": "rgba(255, 108, 55, .16)",
    "aa-accent-wash": "rgba(255, 108, 55, .08)",
    "aa-fg-rgb": "255, 255, 255",

    "aa-ok": "#2ea043",
    "aa-ok-strong": "#238636",
    "aa-warn": "#d29922",
    "aa-bad": "#f85149",
    "aa-bad-strong": "#da3633",
    "aa-info": "#58a6ff",

    # Surfaces: a lift ladder above a pure black canvas.
    "aa-canvas": "#000000",
    "aa-rail": "#040506",
    "aa-panel": "#0d0f12",
    "aa-panel-alt": "#121519",
    "aa-elevated": "#191c21",
    "aa-overlay": "#20242a",
    "aa-hover": "#1a1d22",
    "aa-active": "#23272e",

    # Edges: the smallest alpha that still resolves as a 1px line on black.
    "aa-line-soft": "rgba(255, 255, 255, .16)",
    "aa-line": "rgba(255, 255, 255, .20)",
    "aa-line-strong": "rgba(255, 255, 255, .32)",
    "aa-line-contrast": "rgba(255, 255, 255, .60)",
    "aa-line-accent": "rgba(255, 108, 55, .55)",

    "aa-surface": "rgba(255, 255, 255, .04)",
    "aa-surface-hover": "rgba(255, 255, 255, .075)",

    "aa-text": "#f2f3f5",
    "aa-text-dim": "#a3a9b4",
    "aa-text-mute": "#8a919c",
    "aa-on-accent": ON_ACCENT,

    "aa-code-bg": "#000000",
    "aa-code-border": "rgba(255, 255, 255, .18)",

    "aa-shadow-1": "0 1px 2px rgba(0, 0, 0, .85)",
    "aa-shadow-2": "0 8px 22px rgba(0, 0, 0, .90)",
    "aa-shadow-3": "0 20px 48px rgba(0, 0, 0, .95)",

    # Box recipe: a raised card on the black canvas.
    "aa-box-fill": "#0d0f12",
    "aa-box-line": "rgba(255, 255, 255, .20)",
    "aa-box-shadow": (
        "inset 0 1px 0 rgba(255, 255, 255, .05), 0 1px 2px rgba(0, 0, 0, .65)"
    ),
    "aa-box-pad": ".75rem .9rem",
    "aa-chip-fill": "rgba(255, 255, 255, .07)",
    "aa-chip-line": "rgba(255, 255, 255, .16)",

    # Native Streamlit theme names, kept in step with the lift ladder.
    "background-color": "#000000",
    "secondary-background-color": "#0d0f12",
    "text-color": "#f2f3f5",
    "secondary-text-color": "#a3a9b4",
    "primary-color": "#ff6c37",
    "code-background-color": "#000000",
}

LIGHT = {
    "aa-accent": "#ff6c37",
    "aa-accent-hover": "#f25c26",
    "aa-accent-press": "#d94c19",
    "aa-accent-rgb": "255, 108, 55",
    "aa-accent-soft": "rgba(255, 108, 55, .14)",
    "aa-accent-wash": "rgba(255, 108, 55, .07)",
    "aa-fg-rgb": "15, 23, 42",

    "aa-ok": "#1f883d",
    "aa-ok-strong": "#1a7f37",
    "aa-warn": "#9a6700",
    "aa-bad": "#cf222e",
    "aa-bad-strong": "#a40e26",
    "aa-info": "#0969da",

    "aa-canvas": "#f6f7fa",
    "aa-rail": "#ffffff",
    "aa-panel": "#ffffff",
    "aa-panel-alt": "#fafbfd",
    "aa-elevated": "#ffffff",
    "aa-overlay": "#ffffff",
    "aa-hover": "#eef0f4",
    "aa-active": "#e6e9ef",

    "aa-line-soft": "rgba(15, 23, 42, .10)",
    "aa-line": "rgba(15, 23, 42, .18)",
    "aa-line-strong": "rgba(15, 23, 42, .32)",
    "aa-line-contrast": "rgba(15, 23, 42, .42)",
    "aa-line-accent": "rgba(255, 108, 55, .55)",

    "aa-surface": "rgba(15, 23, 42, .035)",
    "aa-surface-hover": "rgba(15, 23, 42, .07)",

    "aa-text": "#12161d",
    "aa-text-dim": "#566070",
    "aa-text-mute": "#7c8592",
    "aa-on-accent": ON_ACCENT,

    "aa-code-bg": "#f1f3f7",
    "aa-code-border": "rgba(15, 23, 42, .12)",

    "aa-shadow-1": "0 1px 2px rgba(16, 24, 40, .07)",
    "aa-shadow-2": "0 6px 18px rgba(16, 24, 40, .10)",
    "aa-shadow-3": "0 16px 40px rgba(16, 24, 40, .14)",

    "aa-box-fill": "#ffffff",
    "aa-box-line": "rgba(15, 23, 42, .18)",
    "aa-box-shadow": "0 1px 2px rgba(16, 24, 40, .07), 0 1px 3px rgba(16, 24, 40, .05)",
    "aa-box-pad": ".75rem .9rem",
    "aa-chip-fill": "rgba(15, 23, 42, .05)",
    "aa-chip-line": "rgba(15, 23, 42, .14)",

    "background-color": "#f6f7fa",
    "secondary-background-color": "#ffffff",
    "text-color": "#12161d",
    "secondary-text-color": "#566070",
    "primary-color": "#ff6c37",
    "code-background-color": "#f1f3f7",
}

# Names kept from the first pass so existing stylesheets keep resolving. Each
# one points at a canonical token instead of repeating a literal, which is what
# kept them drifting apart before.
ALIASES = {
    "aa-border": "var(--aa-line)",
    "aa-border-strong": "var(--aa-line-strong)",
    "aa-panel-bg": "var(--aa-rail)",
    "aa-panel-border": "var(--aa-line)",
    "border-color": "var(--aa-line)",
    "secondary-background-color": "var(--aa-rail)",
    "code-background-color": "var(--aa-code-bg)",
    "st-background-color": "var(--aa-canvas)",
    "st-secondary-background-color": "var(--aa-panel)",
    "st-text-color": "var(--aa-text)",
    "st-secondary-text-color": "var(--aa-text-dim)",
    "st-border-color": "var(--aa-line)",
    "st-primary-color": "var(--aa-accent)",
    "st-code-background-color": "var(--aa-code-bg)",
}

PALETTES = {"dark": DARK, "light": LIGHT}

# The product ships on the black workspace by default.
DEFAULT_THEME = "dark"


def palette(theme: str = DEFAULT_THEME) -> dict[str, str]:
    """Return the resolved token map for a theme name.

    Args:
        theme (str): Requested theme; unknown values fall back to dark.

    Returns:
        dict[str, str]: Token name to CSS value mapping, aliases included.
    """
    name = str(theme or DEFAULT_THEME).lower()
    base = PALETTES.get(name, PALETTES[DEFAULT_THEME])
    resolved = dict(base)
    for alias, value in ALIASES.items():
        resolved.setdefault(alias, value)
    return resolved


def token_names() -> list[str]:
    """Return every token name declared by the dark palette.

    Returns:
        list[str]: Canonical token names, without the leading dashes.
    """
    return sorted(palette(DEFAULT_THEME))


def css_variables(theme: str = DEFAULT_THEME, selector: str = ":root") -> str:
    """Render the design tokens as a CSS custom property block.

    Args:
        theme (str): Requested theme; unknown values fall back to dark.
        selector (str): Selector that receives the declarations.

    Returns:
        str: A rule declaring every token, radius, speed, and font value.
    """
    tokens = {
        **palette(theme),
        **RADII,
        **MOTION,
        **FONTS,
    }
    lines = [selector + " {", "    color-scheme: " + str(theme).lower() + ";"]
    for name, value in tokens.items():
        lines.append("    --" + name + ": " + value + ";")
    lines.append("}")
    return "\n".join(lines)
