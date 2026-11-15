"""Styles for the request tab strip and its controls."""

REQUEST_TAB_CSS = """
<style>
/* A compact Postman-like request strip that keeps tab controls predictable. */
.st-key-request-tabbar {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    justify-content: flex-start !important;
    align-items: stretch !important;
    gap: 0 !important;
    height: 46px !important;
    min-height: 46px !important;
    max-height: 46px !important;
    overflow-x: auto;
    overflow-y: hidden;
    max-width: 100%;
    border-bottom: 1px solid rgba(var(--aa-fg-rgb),.35);
    scrollbar-width: thin;
}

/* Streamlit may insert layout wrappers. They retain their content width. */
.st-key-request-tabbar > * {
    flex: 0 0 auto !important;
    margin: 0 !important;
}
.st-key-request-tabbar > *:has(> [class*="st-key-request-tab-"]),
.st-key-request-tabbar > [class*="st-key-request-tab-"] {
    width: 220px !important;
    min-width: 220px !important;
    max-width: 220px !important;
}

/* One request tab: label fills the available space and close is fixed. */
div[class*="st-key-request-tab-"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 0 !important;
    align-items: center !important;
    width: 100%;
    height: 44px !important;
    min-height: 44px !important;
    max-height: 44px !important;
    overflow: hidden;
    box-sizing: border-box;
    border-right: 1px solid rgba(var(--aa-fg-rgb),.25);
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
}
div[class*="st-key-request-tab-on-"] {
    border-bottom: 2px solid var(--aa-accent);
    background: rgba(var(--aa-fg-rgb),.12);
}
div[class*="st-key-request-tab-off-"]:hover { background: rgba(var(--aa-fg-rgb),.08); }
div[class*="st-key-request-tab-"] > * { min-width: 0 !important; }
div[class*="st-key-request-tab-"] > *:first-child {
    flex: 1 1 0 !important;
    width: auto !important;
    overflow: hidden;
}
div[class*="st-key-request-tab-"] > *:last-child {
    flex: 0 0 34px !important;
    width: 34px !important;
    min-width: 34px !important;
}

/* Flat controls preserve visual hierarchy while keeping the strip compact. */
.st-key-request-tabbar button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    min-height: 2.1rem;
    padding: .2rem .6rem;
    font-size: .85rem;
}
.st-key-request-tabbar [data-testid="stButton"] { width: 100%; }
div[class*="st-key-request-tab-"] button {
    width: 100% !important;
    justify-content: flex-start !important;
    overflow: hidden;
}
.st-key-request-tabbar button > div { min-width: 0; overflow: hidden; }
.st-key-request-tabbar button p {
    font-size: .85rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
div[class*="st-key-request-close-"] button {
    width: 34px !important;
    min-width: 34px !important;
    max-width: 34px !important;
    height: 42px !important;
    min-height: 42px !important;
    padding: 0 !important;
    justify-content: center !important;
    opacity: .7;
    font-size: 1.25rem !important;
}
div[class*="st-key-request-close-"] {
    display: flex !important;
    flex: 0 0 34px !important;
    width: 34px !important;
    min-width: 34px !important;
    max-width: 34px !important;
    margin-left: 0 !important;
    overflow: visible !important;
}
div[class*="st-key-request-close-"] [data-testid="stButton"] {
    flex: 0 0 34px !important;
    width: 34px !important;
    min-width: 34px !important;
}
div[class*="st-key-request-close-"] button:hover {
    opacity: 1;
    background: rgba(var(--aa-fg-rgb),.2) !important;
}

/* The add control follows the final tab at the left edge of the strip. */
.st-key-request-tabbar > *:has(> .st-key-request-add),
.st-key-request-tabbar > .st-key-request-add {
    width: 44px !important;
    min-width: 44px !important;
    max-width: 44px !important;
}
.st-key-request-add {
    display: flex !important;
    flex: 0 0 44px !important;
    width: 44px !important;
    min-width: 44px !important;
    max-width: 44px !important;
    margin-left: 0 !important;
}
.st-key-request-add [data-testid="stButton"] {
    flex: 0 0 44px !important;
    width: 44px !important;
    min-width: 44px !important;
}
.st-key-request-add button {
    width: 44px !important;
    min-width: 44px !important;
    max-width: 44px !important;
    height: 42px !important;
    min-height: 42px !important;
    padding: 0 !important;
    font-size: 1.3rem !important;
}
</style>
"""
