# frontend/styles/light.py

"""
Light-palette repaint of native Streamlit chrome.

Streamlit bakes its theme into generated class rules at session start and exposes
no theme custom properties, so the palette cannot be flipped at runtime from
Python. Everything the app draws itself already follows the ``--aa-*`` tokens and
needs no branch here. This module covers only the surfaces Streamlit paints: the
app shell, the sidebar, widget fills, menus, code, alerts, chat bubbles, and the
frames around canvas grids.

Injected for the app's single supported light theme.
"""

LIGHT_CSS = """
<style>
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
[data-testid="stMainBlockContainer"], [data-testid="stBottom"],
[data-testid="stBottomBlockContainer"], [data-testid="stAppViewBlockContainer"],
.main, .block-container {
    background: var(--aa-canvas) !important;
    background-image: none !important;
    color: var(--aa-text) !important;
}
[data-testid="stSidebar"], [data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"], [data-testid="stSidebarNav"] {
    background: var(--aa-rail) !important;
    color: var(--aa-text) !important;
}

/* Type */
[data-testid="stMarkdownContainer"] :is(p, h1, h2, h3, h4, h5, h6, li, strong, em, span, td, th),
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p, [data-testid="stText"],
[data-testid="stMetricValue"], [data-testid="stMetricLabel"],
[data-testid="stCaptionContainer"] p,
div[data-testid="stExpander"] summary, div[data-testid="stExpander"] summary p,
button[data-baseweb="tab"], button[data-baseweb="tab"] p,
[data-testid="stTable"] td, [data-testid="stTable"] th { color: var(--aa-text) !important; }
[data-testid="stCaptionContainer"] p, [data-testid="stMetricLabel"] p { color: var(--aa-text-dim) !important; }
[data-testid="stMarkdownContainer"] a { color: var(--aa-accent) !important; }
[data-testid="stMarkdownContainer"] blockquote {
    color: var(--aa-text-dim) !important; border-left-color: var(--aa-line-strong) !important;
}

/* Inputs */
[data-baseweb="input"] > div, [data-baseweb="base-input"], [data-baseweb="textarea"],
[data-baseweb="select"] > div, div[data-testid="stNumberInputContainer"],
[data-testid="stFileUploaderDropzone"] {
    background: var(--aa-panel-alt) !important;
    color: var(--aa-text) !important;
    border-color: var(--aa-line-contrast) !important;
}
input, textarea { color: var(--aa-text) !important; background: transparent !important; }
input::placeholder, textarea::placeholder { color: var(--aa-text-mute) !important; opacity: 1 !important; }
[data-baseweb="select"] svg { color: var(--aa-text-dim) !important; }

/* Menus, popovers, dialogs, toasts, tooltips */
[data-testid="stPopoverBody"], div[data-baseweb="popover"] > div, div[data-baseweb="menu"],
[role="listbox"], [role="option"], [data-baseweb="tooltip"], div[role="dialog"],
[data-testid="stDialog"] > div, div[data-testid="stToast"], div[data-testid="stNotification"] {
    background: var(--aa-elevated) !important;
    color: var(--aa-text) !important;
    border-color: var(--aa-line-strong) !important;
}
[role="option"]:hover, [aria-selected="true"][role="option"] { background: var(--aa-hover) !important; }

/* Boxes */
[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="stExpander"] details,
[data-testid="stForm"], div[data-testid="stMetric"], [data-testid="stExpanderDetails"],
[data-testid="stAlertContainer"], [data-testid="stAlert"], [data-testid="stChatMessage"],
[data-testid="stTabs"], [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    background: var(--aa-box-fill) !important;
    color: var(--aa-text) !important;
    border-color: var(--aa-box-line) !important;
}

/* Code */
div[data-testid="stCode"], div[data-testid="stCodeBlock"], pre, pre code {
    background: var(--aa-code-bg) !important;
    color: var(--aa-text) !important;
    border-color: var(--aa-code-border) !important;
}
[data-testid="stMarkdownContainer"] :not(pre) > code {
    background: var(--aa-chip-fill) !important;
    color: var(--aa-text) !important;
}

/* Buttons */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    background: transparent !important;
    color: var(--aa-text) !important;
    border: 1px solid var(--aa-line-strong) !important;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"]  {
    background: var(--aa-accent) !important;
    color: var(--aa-on-accent) !important;
    border-color: var(--aa-accent) !important;
}
.stButton > button[kind="primary"] p, .stButton > button[kind="primary"] svg,
.stFormSubmitButton > button[kind="primary"] p, .stFormSubmitButton > button[kind="primary"] svg {
    color: var(--aa-on-accent) !important; fill: var(--aa-on-accent) !important;
}

/* Segmented buttons otherwise inherit Streamlit's dark-theme ink in Light. */
[data-testid="stButtonGroup"] button,
[data-baseweb="button-group"] button {
    color: var(--aa-text) !important;
}
[data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stButtonGroup"] button[aria-pressed="true"],
[data-baseweb="button-group"] button[aria-checked="true"],
[data-baseweb="button-group"] button[aria-pressed="true"] {
    background: var(--aa-accent) !important;
    border-color: var(--aa-accent) !important;
    color: var(--aa-on-accent) !important;
}
[data-testid="stButtonGroup"] button[aria-checked="true"] *,
[data-testid="stButtonGroup"] button[aria-pressed="true"] *,
[data-baseweb="button-group"] button[aria-checked="true"] *,
[data-baseweb="button-group"] button[aria-pressed="true"] * {
    color: var(--aa-on-accent) !important;
    fill: var(--aa-on-accent) !important;
}

/* Tabs and controls */
div[data-baseweb="tab-list"] { background: transparent !important; }
button[data-baseweb="tab"] { background: transparent !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--aa-accent) !important; }
div[data-baseweb="tab-highlight"] { background: var(--aa-accent) !important; }
div[data-baseweb="tab-border"] { background: var(--aa-line) !important; }

[data-testid="stCheckbox"] label > div:first-child,
[data-testid="stRadio"] label > div:first-child,
[data-baseweb="checkbox"] span {
    background: var(--aa-panel-alt) !important;
    border-color: var(--aa-line-contrast) !important;
}
[data-testid="stProgress"] > div > div { background: var(--aa-hover) !important; }
[data-testid="stSpinner"] > div { border-top-color: var(--aa-accent) !important; }

hr, [data-testid="stDivider"] hr { border-color: var(--aa-line) !important; }

/* Canvas pieces keep their own painting; the frame is ours. */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    border: 1px solid var(--aa-line-strong) !important;
    border-radius: var(--aa-radius-sm) !important;
    overflow: hidden;
}
</style>
"""
