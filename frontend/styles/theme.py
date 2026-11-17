# frontend/styles/theme.py

"""
Theme hardening and responsive rules.

Streamlit paints some native pieces outside its theme variables. Those pieces
are re-pointed at the ``--aa-*`` tokens here, so switching the palette updates
native widgets and app surfaces together instead of leaving grey patches.
Every rule is token driven; this module carries no colour literals except the
contrast-safe text on the accent fill.
"""

THEME_CSS = """
<style>
[data-testid="stApp"], .stApp { color: var(--aa-text); }
[data-testid="stSidebar"] { color: var(--aa-text); }

/* Header and toolbar actions. */
[data-testid="stToolbar"] button,
[data-testid="stHeaderActionElements"] button,
button[data-testid="stBaseButton-header"],
button[data-testid="stBaseButton-headerNoPadding"] {
    color: var(--aa-text-dim) !important;
    background: transparent !important;
}
[data-testid="stToolbar"] button:hover,
[data-testid="stHeaderActionElements"] button:hover {
    color: var(--aa-text) !important;
    background: var(--aa-hover) !important;
}

/* Popover, dropdown and tooltip surfaces. */
[data-testid="stPopoverBody"],
div[data-baseweb="popover"] > div,
div[data-baseweb="tooltip"] {
    background: var(--aa-elevated) !important;
    border: 1px solid var(--aa-border) !important;
    border-radius: var(--aa-radius-sm) !important;
    box-shadow: var(--aa-shadow-2) !important;
    color: var(--aa-text) !important;
}

/* Toasts float above the workspace and follow the palette. */
div[data-testid="stToast"] {
    background: var(--aa-elevated) !important;
    border: 1px solid var(--aa-border-strong) !important;
    border-radius: var(--aa-radius-sm) !important;
    box-shadow: var(--aa-shadow-3) !important;
    color: var(--aa-text) !important;
}

/* Checkboxes, radios, sliders, progress and spinners. */
div[data-testid="stCheckbox"] label span,
div[data-testid="stRadio"] label span {
    border-color: var(--aa-border-strong) !important;
}

div[data-testid="stSlider"] [role="slider"] { background: var(--aa-accent) !important; }
div[data-testid="stProgress"] > div > div > div { background: var(--aa-accent) !important; }
div[data-testid="stSpinner"] i { border-top-color: var(--aa-accent) !important; }

/* Segmented controls: the selected pill uses the accent fill. */
div[data-testid="stButtonGroup"] button,
              div[data-baseweb="button-group"] button {
    background: var(--aa-panel) !important;
    color: var(--aa-text-dim) !important;
    border-color: var(--aa-border) !important;
    border-radius: 999px !important;
    font-weight: 600;
}

div[data-testid="stButtonGroup"] button[aria-checked="true"],
div[data-testid="stButtonGroup"] button[aria-pressed="true"],
div[data-baseweb="button-group"] button[aria-checked="true"] {
    background: var(--aa-accent) !important;
    border-color: var(--aa-accent) !important;
    color: #ffffff !important;
}

/* Tabs, metrics and notices. */
div[data-baseweb="tab-highlight"] { background: var(--aa-accent) !important; }
div[data-baseweb="tab-border"] { background: var(--aa-border) !important; }
div[data-testid="stMetricValue"] { color: var(--aa-text); }
[data-testid="stNotification"] {
    background: var(--aa-elevated) !important;
    border: 1px solid var(--aa-border) !important;
    color: var(--aa-text) !important;
}

/* Selection, links and dividers. */
a, a:visited { color: var(--aa-accent) !important; }
::selection { background: var(--aa-accent-soft); color: var(--aa-text); }

/* Sticky toolbars keep the actions in reach in long workspaces. */
.st-key-test-case-toolbar {
    position: sticky; top: 0; z-index: 4;
    padding-block: .35rem; margin-bottom: .35rem;
    background: var(--aa-canvas);
    border-bottom: 1px solid var(--aa-border);
}

/* Dense rows only. Container gaps stay Streamlit's own, because heading and
   caption margins are what keep a title from colliding with the row below it. */
div[class*="st-key-collection-tree-row-"] [data-testid="stHorizontalBlock"],
div[class*="st-key-browser-request-row-"] [data-testid="stHorizontalBlock"],
.st-key-test-case-toolbar [data-testid="stHorizontalBlock"] { gap: .3rem; }

/* Responsive. */
@media (max-width: 1440px) {
    .block-container { max-width: 1280px; }
}
@media (max-width: 1024px) {
    .block-container {
        max-width: 100%;
        padding-left: 1rem !important; padding-right: 1rem !important;
    }
    .st-key-collection-browser-header { position: static; }
}
@media (max-width: 768px) {
    .block-container {
        padding-left: .6rem !important; padding-right: .6rem !important;
    }
    .st-key-test-case-toolbar { position: static; }
    div[data-testid="stHorizontalBlock"] { gap: .4rem; }
}
@media (prefers-reduced-motion: reduce) {
    .st-key-test-case-toolbar, .st-key-collection-browser-header { transition: none; }
}
</style>
"""
