# frontend/styles/surfaces.py

"""
Surface layer: the box recipe and the edges of native Streamlit surfaces.

Every rule here reads ``--aa-*`` tokens and paints the single light workspace.
The module has two jobs.

1. ``.aa-box`` and its variants give application code one card recipe instead of
   per-page border and padding guesses.
2. The native hooks give Streamlit's own containers an explicit edge and keep
   nested controls distinct from the pale canvas.

Nested boxes fall back to ``--aa-line-soft`` and ``--aa-panel-alt`` so a card
inside a card reads as a child rather than as a second frame.
"""

SURFACES_CSS = """
<style>
/* ---------- Card recipe ---------- */
.aa-box,
.aa-box-quiet,
.aa-box-inset,
.aa-box-raised {
    box-sizing: border-box;
    border: 1px solid var(--aa-box-line);
    border-radius: var(--aa-radius-md);
    padding: var(--aa-box-pad);
    transition: border-color var(--aa-fast) var(--aa-ease),
                background var(--aa-fast) var(--aa-ease),
                box-shadow var(--aa-fast) var(--aa-ease);
}
.aa-box {
    background: var(--aa-box-fill);
    box-shadow: var(--aa-box-shadow);
}
.aa-box-quiet {
    background: transparent;
    border-color: var(--aa-line-soft);
    box-shadow: none;
}
.aa-box-inset {
    background: var(--aa-canvas);
    border-color: var(--aa-line-soft);
    box-shadow: none;
}
.aa-box-raised {
    background: var(--aa-elevated);
    border-color: var(--aa-line-strong);
    box-shadow: var(--aa-shadow-2);
}
.aa-box:hover {
    border-color: var(--aa-line-strong);
}
.aa-box-selected,
.aa-box.is-selected {
    background: var(--aa-box-fill);
    border-color: var(--aa-line-accent);
    box-shadow: var(--aa-box-shadow), 0 0 0 3px var(--aa-accent-soft);
}

/* ---------- Small primitives ---------- */
.aa-chip {
    display: inline-flex;
    align-items: center;
    gap: .3rem;
    padding: .1rem .45rem;
    border-radius: var(--aa-radius-pill);
    border: 1px solid var(--aa-chip-line);
    background: var(--aa-chip-fill);
    font: 600 .7rem/1.5 var(--aa-font-mono);
    white-space: nowrap;
}
.aa-chip-accent { color: var(--aa-accent); border-color: var(--aa-line-accent); }
.aa-chip-ok { color: var(--aa-ok); border-color: rgba(46, 158, 91, .38); }
.aa-chip-bad { color: var(--aa-bad); border-color: rgba(229, 72, 77, .38); }
.aa-chip-warn { color: var(--aa-warn); border-color: rgba(210, 153, 34, .38); }

.aa-row {
    display: flex;
    align-items: center;
    gap: .6rem;
    min-width: 0;
    padding: .45rem .6rem;
    border-bottom: 1px solid var(--aa-line-soft);
}
.aa-row:last-child { border-bottom: 0; }
.aa-row:hover { background: var(--aa-surface-hover); }
.aa-row-meta { min-width: 0; flex: 1 1 auto; overflow: hidden; }
.aa-row-value {
    font: 600 .74rem/1.3 var(--aa-font-mono);
    color: var(--aa-text-dim);
    white-space: nowrap;
    text-align: right;
}
.aa-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

/* ---------- Native containers ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid var(--aa-box-line) !important;
    border-radius: var(--aa-radius-md) !important;
    background: var(--aa-box-fill) !important;
}
[data-testid="stExpanderDetails"] [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stPopoverBody"] [data-testid="stVerticalBlockBorderWrapper"],
[role="dialog"] [data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--aa-line-soft) !important;
    background: var(--aa-panel-alt) !important;
}

/* Expanders: header, body, and one shared edge. */
div[data-testid="stExpander"] details {
    border: 1px solid var(--aa-box-line) !important;
    border-radius: var(--aa-radius-md) !important;
    background: var(--aa-box-fill) !important;
    overflow: hidden;
}
div[data-testid="stExpander"] summary {
    padding: .45rem .6rem;
    border-radius: var(--aa-radius-sm);
    transition: background var(--aa-fast) var(--aa-ease);
}
div[data-testid="stExpander"] details:hover > summary {
    background: var(--aa-surface-hover);
}
div[data-testid="stExpander"] summary p { font-weight: 620; }
[data-testid="stExpanderDetails"] {
    border-top: 1px solid var(--aa-line-soft);
    background: transparent;
}

/* Forms, metrics, alerts, chat, tabs, code. */
[data-testid="stForm"] {
    border: 1px solid var(--aa-box-line) !important;
    border-radius: var(--aa-radius-md) !important;
    background: var(--aa-box-fill);
}
[data-testid="stMetric"] {
    border: 1px solid var(--aa-line-soft) !important;
    border-radius: var(--aa-radius-sm) !important;
    background: var(--aa-panel-alt) !important;
    padding: .4rem .55rem !important;
}
[data-testid="stAlertContainer"],
[data-testid="stAlert"],
[data-testid="stNotification"] {
    border: 1px solid var(--aa-line) !important;
    border-radius: var(--aa-radius-sm) !important;
    background: var(--aa-elevated) !important;
    color: var(--aa-text) !important;
}
[data-testid="stChatMessage"] {
    border: 1px solid var(--aa-line-soft) !important;
    border-radius: var(--aa-radius-md) !important;
    background: var(--aa-panel-alt) !important;
    padding: .55rem .75rem !important;
}
/* Project chat uses asymmetric, shaded bubbles and keeps timestamps above them. */
.st-key-project-chat-transcript [class*="st-key-chat-bubble-assistant"] {
    box-sizing: border-box;
    width: 66.666% !important;
    max-width: 66.666% !important;
    margin-right: auto !important;
    padding: .55rem .75rem;
    border: 1px solid var(--aa-line-strong);
    border-radius: 14px 14px 14px 4px;
    background: var(--aa-panel-alt) !important;
}
.st-key-project-chat-transcript [class*="st-key-chat-bubble-user"] {
    box-sizing: border-box;
    width: 66.666% !important;
    max-width: 66.666% !important;
    margin-left: auto !important;
    padding: .55rem .75rem;
    border: 1px solid var(--aa-line-accent);
    border-radius: 14px 14px 4px 14px;
    background: var(--aa-accent-wash) !important;
}
.st-key-project-chat-transcript [class*="st-key-chat-time-user"] {
    text-align: right !important;
}
.st-key-project-chat-transcript [class*="st-key-chat-time-user"] [data-testid="stCaptionContainer"] {
    text-align: right !important;
}
.st-key-project-chat-transcript [class*="st-key-chat-time-"],
.st-key-project-chat-transcript [class*="st-key-chat-bubble-"] {
    width: 66.666% !important;
    max-width: 66.666% !important;
}
.st-key-project-chat-transcript [class*="st-key-chat-bubble-"] [data-testid="stExpander"] details {
    border: 0 !important;
    border-radius: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
}
.st-key-project-chat-transcript [class*="st-key-chat-bubble-"] [data-testid="stExpander"] summary {
    padding: .2rem 0 !important;
    color: var(--aa-text-dim) !important;
}
.st-key-project-chat-transcript [class*="st-key-chat-bubble-"] [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    margin: -1px !important;
    padding: 0 !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    white-space: nowrap !important;
    border: 0 !important;
}
/* Keep the chat composer visibly separated from the light canvas. */
[data-testid="stChatInput"] {
    background: var(--aa-panel-alt) !important;
    border: 1px solid var(--aa-line-contrast) !important;
    border-radius: var(--aa-radius-sm) !important;
    padding: .25rem .4rem !important;
}
/* Keep the composer in normal document flow with the conversation. */
div[class*="st-key-project-chat-composer-"] {
    padding-top: .45rem;
}
[data-testid="stChatInput"]:focus-within {
    border-color: var(--aa-accent) !important;
    box-shadow: 0 0 0 3px var(--aa-accent-soft) !important;
}
[data-testid="stChatInput"] [data-baseweb="textarea"] {
    background: transparent !important;
    color: var(--aa-text) !important;
    border: 0 !important;
    box-shadow: none !important;
}
[data-testid="stChatInput"] textarea {
    background: transparent !important;
    color: var(--aa-text) !important;
    border: 0 !important;
    box-shadow: none !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: var(--aa-text-mute) !important;
    opacity: 1 !important;
}
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    border-bottom: 1px solid var(--aa-line-soft) !important;
    gap: .1rem;
}
@media (max-width: 768px) {
    .st-key-project-chat-transcript [class*="st-key-chat-time-"],
    .st-key-project-chat-transcript [class*="st-key-chat-bubble-"] {
        width: 92% !important;
        max-width: 92% !important;
    }
}
[data-baseweb="tab"] {
    border-radius: var(--aa-radius-xs) var(--aa-radius-xs) 0 0 !important;
    padding: .4rem .8rem !important;
    font-size: .88rem !important;
}
[data-baseweb="tab"][aria-selected="true"] { color: var(--aa-accent) !important; }
[data-baseweb="tab"][aria-selected="true"] p { color: var(--aa-accent) !important; }
[data-baseweb="tab-highlight"] { background: var(--aa-accent) !important; }
[data-baseweb="tab-border"] { background: var(--aa-line) !important; }

div[data-testid="stCode"],
div[data-testid="stCodeBlock"],
pre {
    border: 1px solid var(--aa-code-border) !important;
    border-radius: var(--aa-radius-sm) !important;
    background: var(--aa-code-bg) !important;
    color: var(--aa-text) !important;
}
pre code { background: transparent !important; color: inherit !important; }
[data-testid="stMarkdownContainer"] :not(pre) > code {
    border: 1px solid var(--aa-line-soft);
    border-radius: var(--aa-radius-xs);
    padding: .05rem .3rem;
    background: var(--aa-chip-fill) !important;
    color: var(--aa-text) !important;
}

/* ---------- Inputs: a visible edge is a usability requirement ---------- */
div[data-testid="stTextInput"] [data-baseweb="base-input"],
div[data-testid="stTextInput"] [data-baseweb="input"] > div,
div[data-testid="stTextInput"] [data-baseweb] > div:has(> input),
div[data-testid="stNumberInput"] [data-baseweb="base-input"],
div[data-testid="stNumberInput"] [data-baseweb="input"] > div,
div[data-testid="stNumberInput"] [data-baseweb] > div:has(> input),
div[data-testid="stDateInput"] [data-baseweb="base-input"],
div[data-testid="stDateInput"] [data-baseweb="input"] > div,
div[data-testid="stDateInput"] [data-baseweb] > div:has(> input),
[data-testid="stTextArea"] [data-baseweb="base-input"],
[data-testid="stTextArea"] [data-baseweb="textarea"],
[data-baseweb="select"] > div,
[data-baseweb="base-input"],
[data-baseweb="textarea"],
[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploaderDropzone"] > div {
    background: var(--aa-panel-alt) !important;
    color: var(--aa-text) !important;
    border: 1px solid var(--aa-line-contrast) !important;
    border-radius: var(--aa-radius-xs) !important;
    transition: border-color var(--aa-fast) var(--aa-ease),
                box-shadow var(--aa-fast) var(--aa-ease);
}
/* The project picker sits in the dark rail, where Streamlit's native select
   outline can disappear against the sidebar surface. Give its control a
   scoped, explicit edge so the selected project stays visually bounded. */
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] > div {
    background: var(--aa-panel-alt) !important;
    color: var(--aa-text) !important;
    border: 1px solid var(--aa-line-contrast) !important;
    border-radius: var(--aa-radius-xs) !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] > div:hover {
    border-color: var(--aa-line-strong) !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
    border-color: var(--aa-accent) !important;
    box-shadow: 0 0 0 3px var(--aa-accent-soft) !important;
}
[data-baseweb="base-input"]:hover,
[data-baseweb="input"] > div:hover,
[data-baseweb="textarea"]:hover,
[data-baseweb="select"] > div:hover {
    border-color: var(--aa-line-strong) !important;
}
[data-baseweb="base-input"]:focus-within,
[data-baseweb="input"] > div:focus-within,
[data-baseweb="textarea"]:focus-within,
[data-baseweb="select"] > div:focus-within {
    border-color: var(--aa-accent) !important;
    box-shadow: 0 0 0 3px var(--aa-accent-soft) !important;
    outline: none !important;
}
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input,
div[data-testid="stTextArea"] textarea {
    background: transparent !important;
    color: var(--aa-text) !important;
    border: 0 !important;
    box-shadow: none !important;
}
input::placeholder,
textarea::placeholder {
    color: var(--aa-text-mute) !important;
    opacity: 1 !important;
}

/* Dropdown, popover, tooltip, and dialog surfaces sit one step above panels. */
[data-testid="stPopoverBody"],
div[data-baseweb="popover"] > div,
div[data-baseweb="menu"],
[role="listbox"],
[data-baseweb="tooltip"],
div[role="dialog"],
div[data-testid="stDialog"] > div {
    background: var(--aa-elevated) !important;
    color: var(--aa-text) !important;
    border: 1px solid var(--aa-line-strong) !important;
    border-radius: var(--aa-radius-sm) !important;
    box-shadow: var(--aa-shadow-2) !important;
}
[role="option"] { padding: .3rem .45rem !important; }
[role="option"]:hover,
[aria-selected="true"][role="option"] {
    background: var(--aa-hover) !important;
    color: var(--aa-text) !important;
}

/* Grids and editors paint on canvas, so the frame is ours to draw. */
div[data-testid="stDataFrame"],
div[data-testid="stDataEditor"] {
    border: 1px solid var(--aa-line-strong) !important;
    border-radius: var(--aa-radius-sm) !important;
    background: var(--aa-panel-alt) !important;
    overflow: hidden;
}

/* Sidebar blocks are children of the rail. */
[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--aa-panel-alt) !important;
}

/* ---------- Buttons ---------- */
.stButton > button,
.stDownloadButton > button,
.stFormSubmitButton > button {
    border: 1px solid var(--aa-line-strong) !important;
    background: transparent !important;
    color: var(--aa-text) !important;
    border-radius: var(--aa-radius-xs) !important;
    font-weight: 600;
    transition: border-color var(--aa-fast) var(--aa-ease),
                background var(--aa-fast) var(--aa-ease),
                color var(--aa-fast) var(--aa-ease);
}
.stButton > button:hover,
.stDownloadButton > button:hover,
.stFormSubmitButton > button:hover {
    border-color: var(--aa-accent) !important;
    background: var(--aa-accent-wash) !important;
}

/* Primary ink is dark on the orange fill: white is only 2.8:1 there. */
.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"] {
    background: var(--aa-accent) !important;
    border-color: var(--aa-accent) !important;
    color: var(--aa-on-accent) !important;
}
.stButton > button[kind="primary"] p,
.stButton > button[kind="primary"] span,
.stButton > button[kind="primary"] svg,
.stFormSubmitButton > button[kind="primary"] p,
.stFormSubmitButton > button[kind="primary"] span,
.stFormSubmitButton > button[kind="primary"] svg {
    color: var(--aa-on-accent) !important;
    fill: var(--aa-on-accent) !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--aa-accent-hover) !important;
    border-color: var(--aa-accent-hover) !important;
}
.stButton > button[kind="primary"]:active {
    background: var(--aa-accent-press) !important;
    border-color: var(--aa-accent-press) !important;
}

/* ---------- Focus ---------- */
:where(button, a, input, textarea, select, [role="option"], [tabindex]):focus-visible {
    outline: 2px solid var(--aa-accent) !important;
    outline-offset: 2px !important;
    border-radius: var(--aa-radius-xs);
}

/* Material icons inside custom-styled buttons inherit the label colour. */
.stButton > button[kind="primary"] [data-testid="stIconMaterial"],
.stFormSubmitButton > button[kind="primary"] [data-testid="stIconMaterial"] {
    color: var(--aa-on-accent) !important;
}
[data-testid="stSidebar"] button[kind="tertiary"] [data-testid="stIconMaterial"] {
    color: var(--aa-text-dim) !important;
}

@media (prefers-reduced-motion: reduce) {
    .aa-box, .aa-box-quiet, .aa-box-inset, .aa-box-raised,
    [data-testid="stVerticalBlockBorderWrapper"],
    div[data-testid="stExpander"] summary {
        transition: none !important;
    }
}
</style>
"""
