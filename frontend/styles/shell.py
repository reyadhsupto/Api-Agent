# frontend/styles/shell.py

"""
Shell styles: brand block, rail navigation, dense surfaces, and polish.

These rules only consume the ``--aa-*`` tokens declared in ``tokens.py``, so the
whole shell follows the active theme without duplication. Selectors are stable
Streamlit ``st-key-*`` hooks or plain data-testids; no layout geometry depends on
widget internals.
"""

SHELL_CSS = """
<style>
.stApp { background: var(--aa-canvas); color: var(--aa-text); }
[data-testid="stAppViewContainer"] { background: var(--aa-canvas); }
[data-testid="stSidebar"] { background: var(--aa-rail); }
[data-testid="stSidebar"] > div:first-child { padding-top: .7rem; }
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stStatusWidget"] { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; height: 0; }

/* Brand block at the top of the rail. */
.aa-rail-brand { display: flex; align-items: center; gap: .55rem; padding: .1rem 0 .6rem; }
.aa-rail-mark {
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; border-radius: 8px; font-weight: 800; font-size: .74rem;
    color: #fff; background: var(--aa-accent); box-shadow: var(--aa-shadow-2);
}
.aa-rail-name { font-size: 1rem; font-weight: 720; letter-spacing: -.02em; }

/* Rail navigation reads as a list, not as form controls. */
[data-testid="stSidebar"] [role="radiogroup"] { gap: .18rem; }
[data-testid="stSidebar"] [role="radiogroup"] label {
    padding: .34rem .5rem; border-radius: var(--aa-radius-xs);
    transition: background var(--aa-fast) var(--aa-ease);
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover { background: var(--aa-hover); }

/* Dense, Postman-like rows and surfaces. */
.aa-panel {
    background: var(--aa-panel); border: 1px solid var(--aa-border);
    border-radius: var(--aa-radius); box-shadow: var(--aa-shadow-1);
}
.aa-section-title {
    margin: .9rem 0 .35rem; font-size: .68rem; font-weight: 700;
    letter-spacing: .08em; text-transform: uppercase; color: var(--aa-text-mute);
}
.aa-mono, code, pre, .aa-request-url { font-family: var(--aa-font-mono) !important; }

/* Compact shared control surfaces. */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-baseweb="select"] > div {
    border-radius: var(--aa-radius-xs) !important;
    border-color: var(--aa-border) !important;
    transition: border-color var(--aa-fast) var(--aa-ease), box-shadow var(--aa-fast) var(--aa-ease);
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stNumberInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: var(--aa-accent) !important;
    box-shadow: 0 0 0 3px var(--aa-accent-soft) !important;
}
div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
    border: 1px solid var(--aa-border); border-radius: var(--aa-radius-sm);
    overflow: hidden; background: var(--aa-panel);
}
div[data-testid="stExpander"] details {
    border: 1px solid var(--aa-border) !important;
    border-radius: var(--aa-radius-sm) !important;
    background: var(--aa-panel);
    transition: border-color var(--aa-fast) var(--aa-ease);
}
div[data-testid="stExpander"] details:hover { border-color: var(--aa-border-strong) !important; }
div[data-testid="stExpander"] summary { font-weight: 600; }

/* Buttons: quiet surfaces, accent only on the primary action. */
.stButton > button, .stDownloadButton > button {
    border-radius: var(--aa-radius-xs) !important;
    border: 1px solid var(--aa-border) !important;
    font-weight: 580; letter-spacing: -.005em;
    transition: background var(--aa-fast) var(--aa-ease),
                border-color var(--aa-fast) var(--aa-ease),
                transform 60ms var(--aa-ease);
}
.stButton > button:hover, .stDownloadButton > button:hover {
    border-color: var(--aa-border-strong) !important; background: var(--aa-hover) !important;
}
.stButton > button[kind="primary"] {
    background: var(--aa-accent) !important; border-color: var(--aa-accent) !important; color: #fff !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--aa-accent-hover) !important; border-color: var(--aa-accent-hover) !important;
}
.stButton > button:active { transform: translateY(1px); }

/* Tabs read as a dense editor strip. */
div[data-baseweb="tab-list"] {
    gap: .1rem; border-bottom: 1px solid var(--aa-border); padding-bottom: 0;
}
button[data-baseweb="tab"] {
    padding: .42rem .78rem; font-size: .84rem; font-weight: 580;
    color: var(--aa-text-dim); border-radius: var(--aa-radius-xs) var(--aa-radius-xs) 0 0;
}
button[data-baseweb="tab"][aria-selected="true"] { color: var(--aa-accent); }
button[data-baseweb="tab"]:hover { background: var(--aa-hover); color: var(--aa-text); }

/* Badges used across request rows and result headers. */
.aa-method-pill, .aa-status-pill {
    display: inline-block; padding: 3px 7px; border-radius: 6px;
    font: 700 .7rem/1.15 var(--aa-font-mono); letter-spacing: .01em; text-align: center;
}
.aa-status-pill.aa-pass { color: var(--aa-ok); background: rgba(var(--aa-fg-rgb), .06); }
.aa-status-pill.aa-fail { color: var(--aa-bad); background: rgba(248, 81, 73, .14); }

/* Code and response bodies. */
div[data-testid="stCode"], div[data-testid="stCodeBlock"] {
    border: 1px solid var(--aa-code-border); border-radius: var(--aa-radius-sm);
    background: var(--aa-code-bg); box-shadow: none;
}
pre { font-variant-ligatures: none; }

/* Scrollbars. */
* { scrollbar-width: thin; scrollbar-color: var(--aa-border-strong) transparent; }
::-webkit-scrollbar { width: 9px; height: 9px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    border: 2px solid transparent; border-radius: 999px; background-clip: content-box;
    background-color: var(--aa-border-strong);
}
::-webkit-scrollbar-thumb:hover { background-color: var(--aa-text-mute); }

/* Keyboard and focus affordances. */
:where(button, input, textarea, [tabindex]):focus-visible {
    outline: 2px solid var(--aa-accent); outline-offset: 2px;
}

/* Responsive density. */
@media (max-width: 1100px) {
    .block-container { padding-left: .9rem !important; padding-right: .9rem !important; }
}
@media (max-width: 760px) {
    .aa-hero-title { font-size: 1.2rem; }
    .aa-stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    div[data-testid="stExpander"] summary { font-size: .86rem; }
}

/* Honour the motion preference everywhere. */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        transition-duration: .01ms !important;
        animation-duration: .01ms !important;
        animation-iteration-count: 1 !important;
    }
}

/* Black canvas: structural surfaces inherit the same base so Streamlit dark
   grey never shows through around the widgets. */
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="stBottomBlockContainer"],
[data-testid="stVerticalBlock"] {
    background: var(--aa-canvas);
}
[data-testid="stSidebar"], [data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"], [data-testid="stSidebarNav"] {
    background: var(--aa-rail) !important;
}
[data-testid="stSidebar"] { border-right: 1px solid var(--aa-border); }
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {
    background: transparent !important;
}

/* Widgets sit one step above the canvas so edges stay visible on pure black. */
[data-baseweb="input"], [data-baseweb="base-input"],
div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input,
div[data-testid="stTextArea"] textarea, div[data-testid="stDateInput"] input,
[data-baseweb="select"] > div, [data-testid="stFileUploaderDropzone"] {
    background: var(--aa-panel) !important;
    color: var(--aa-text) !important;
    border-color: var(--aa-border) !important;
}
[data-baseweb="select"] svg { color: var(--aa-text-dim) !important; }
[data-baseweb="popover"], [data-baseweb="menu"],
[role="listbox"], [role="option"] {
    background: var(--aa-elevated) !important;
    color: var(--aa-text) !important;
}
[role="option"]:hover, [aria-selected="true"][role="option"] { background: var(--aa-hover) !important; }

/* Panels, framed containers, codes and tables. */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--aa-panel);
    border-color: var(--aa-border) !important;
}
div[data-testid="stExpander"] details {
    background: var(--aa-panel) !important;
    border-color: var(--aa-border) !important;
}
div[data-testid="stExpander"] summary:hover { background: var(--aa-hover) !important; }
div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
    background: var(--aa-panel); border: 1px solid var(--aa-border);
}
div[data-testid="stDataFrame"] [role="columnheader"],
div[data-testid="stDataEditor"] [role="columnheader"] { background: var(--aa-elevated); }
div[data-testid="stAlertContainer"] {
    background: var(--aa-elevated); border-radius: var(--aa-radius-sm);
}
div[data-testid="stMetric"] {
    background: var(--aa-panel); border: 1px solid var(--aa-border);
    border-radius: var(--aa-radius-sm); padding: .45rem .6rem;
}
[data-testid="stForm"] {
    background: var(--aa-panel); border: 1px solid var(--aa-border);
    border-radius: var(--aa-radius-sm);
}
div[data-testid="stCode"], div[data-testid="stCodeBlock"], pre, code {
    background: var(--aa-code-bg) !important; color: var(--aa-text) !important;
}
hr { border-color: var(--aa-border) !important; }
.stCaption p, [data-testid="stCaptionContainer"] p { color: var(--aa-text-mute); }
[data-testid="stMarkdownContainer"] a { color: var(--aa-accent); }

</style>
"""
