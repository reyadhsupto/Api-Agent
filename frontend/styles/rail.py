# frontend/styles/rail.py

"""
Collection rail: tree rows that read as boxes instead of floating text.

On a pure black canvas a transparent row has no edge at all, so a collection and
its requests blurred together. Each collection row is therefore a filled card
with a declared border, and each request row is anchored to the collection by a
guide line plus an accent bar on the active row. Selection is carried by the
accent edge, never by fill alone, so it survives both palettes.

All values resolve from ``--aa-*`` tokens. The light palette flips the tokens, so
these rules need no light-mode branch.
"""

RAIL_CSS = """
<style>
/* Collection rows are cards: fill plus edge, so they separate on black. */
div[class*="st-key-collection-tree-row-"] {
    box-sizing: border-box;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    margin: 4px 0;
    padding: 5px 7px;
    background: var(--aa-panel-alt);
    border: 1px solid var(--aa-line-soft) !important;
    border-radius: var(--aa-radius-sm);
    transition: border-color var(--aa-fast) var(--aa-ease),
                background var(--aa-fast) var(--aa-ease);
}
div[class*="st-key-collection-tree-row-"]:hover {
    border-color: var(--aa-line-strong) !important;
    background: var(--aa-hover);
}
div[class*="st-key-collection-tree-row-selected-"] {
    border-color: var(--aa-line-accent) !important;
    background: var(--aa-accent-wash);
    box-shadow: inset 2px 0 0 var(--aa-accent);
}

/* A partial collection keeps its edge but dims the mark. */
div[class*="st-key-collection-tree-row-partial-"] [data-testid="stCheckbox"] {
    opacity: .72;
}

/* Request rows hang under the collection, joined by the guide line. */
div[class*="st-key-browser-request-row-"] {
    box-sizing: border-box;
    width: 100%;
    max-width: 100%;
    min-width: 0;
    margin: 1px 0;
    padding: 1px 5px 1px 14px;
    position: relative;
    background: transparent;
    border: 1px solid transparent !important;
    border-left: 2px solid transparent !important;
    border-radius: var(--aa-radius-xs);
    transition: background var(--aa-fast) var(--aa-ease),
                border-color var(--aa-fast) var(--aa-ease);
}
div[class*="st-key-browser-request-row-"]:hover,
div[class*="st-key-browser-request-row-"]:focus-within {
    background: var(--aa-hover);
    border-color: var(--aa-line-soft) !important;
    border-left-color: var(--aa-line-strong) !important;
}
div[class*="st-key-browser-request-row-selected-"] {
    background: var(--aa-accent-wash) !important;
    border-left-color: var(--aa-accent) !important;
}
div[class*="st-key-browser-request-row-"]::before {
    content: "";
    position: absolute;
    left: 5px;
    top: 0;
    bottom: 0;
    border-left: 1px solid var(--aa-line-soft);
    pointer-events: none;
}

/* Row type: names carry the weight, URLs stay secondary and clipped. */
div[class*="st-key-collection-tree-row-"] [data-testid="stButton"] button p,
div[class*="st-key-browser-request-row-"] [data-testid="stButton"] button p {
    font-weight: 600;
}
div[class*="st-key-browser-request-row-"] [data-testid="stButton"] button p {
    font-weight: 560;
    font-size: .84rem;
}
div[class*="st-key-collection-tree-row-"] :is([data-testid="column"], [data-testid="stColumn"]),
div[class*="st-key-browser-request-row-"] :is([data-testid="column"], [data-testid="stColumn"]),
.st-key-navigator-search-row :is([data-testid="column"], [data-testid="stColumn"]) {
    min-width: 0;
    padding: 0;
}

/* Three-dot triggers: quiet at rest, accent on hover or focus. */
div[class*="st-key-collection-tree-row-"] [data-testid="stPopover"] > button,
div[class*="st-key-browser-request-row-"] [data-testid="stPopover"] > button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.6rem;
    min-width: 1.6rem;
    height: 1.8rem;
    min-height: 1.8rem;
    padding: 0 !important;
    border: 0 !important;
    border-radius: var(--aa-radius-xs) !important;
    background: transparent !important;
    box-shadow: none !important;
    color: var(--aa-text-dim);
    opacity: .55;
    transition: opacity var(--aa-fast) var(--aa-ease),
                color var(--aa-fast) var(--aa-ease),
                background var(--aa-fast) var(--aa-ease);
}
div[class*="st-key-collection-tree-row-"]:hover [data-testid="stPopover"] > button,
div[class*="st-key-browser-request-row-"]:hover [data-testid="stPopover"] > button,
div[class*="st-key-collection-tree-row-"] [data-testid="stPopover"] > button:focus-visible,
div[class*="st-key-browser-request-row-"] [data-testid="stPopover"] > button:focus-visible {
    opacity: 1;
    color: var(--aa-accent);
    background: var(--aa-accent-wash) !important;
}

/* The rail scroll body owns its scrollbar. */
.st-key-collection-browser-scroll {
    scrollbar-gutter: stable;
}
.st-key-collection-browser-scroll::-webkit-scrollbar { width: 7px; }
.st-key-collection-browser-scroll::-webkit-scrollbar-thumb {
    border-radius: var(--aa-radius-pill);
    background: var(--aa-line-strong);
}
.st-key-collection-browser-scroll::-webkit-scrollbar-track { background: transparent; }

@media (hover: none) {
    div[class*="st-key-collection-tree-row-"] [data-testid="stPopover"] > button,
    div[class*="st-key-browser-request-row-"] [data-testid="stPopover"] > button {
        opacity: .8;
    }
}
</style>
"""
