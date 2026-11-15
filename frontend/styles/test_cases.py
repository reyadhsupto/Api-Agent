"""Styles for the test-case workspace, cards and toolbar."""

TEST_CASE_CSS = """
<style>
.st-key-test-case-toolbar { container-type: inline-size; min-width: 0; }
.st-key-test-run-manager { container-type: inline-size; min-width: 0; }
.st-key-test-case-quick-actions { container-type: inline-size; min-width: 0; }
.st-key-test-cases-workspace { container-type: inline-size; min-width: 0; }
div[class*="st-key-tc-card-"] {
    container-type: inline-size;
    border-left: 4px solid rgba(var(--aa-fg-rgb),.38) !important;
    border-radius: .65rem !important;
    min-width: 0;
}
div[class*="st-key-tc-card-passed-"] { border-left-color: var(--aa-ok) !important; }
div[class*="st-key-tc-card-failed-"] { border-left-color: var(--aa-bad) !important; }
div[class*="st-key-tc-card-error-"] { border-left-color: var(--aa-warn) !important; }
div[class*="st-key-manual_pass_"] button {
    background: var(--aa-ok) !important; border-color: var(--aa-ok) !important; color: #fff !important;
}
div[class*="st-key-manual_pass_"] button:hover { background: var(--aa-ok-strong) !important; border-color: var(--aa-ok-strong) !important; }
div[class*="st-key-manual_fail_"] button {
    background: var(--aa-bad) !important; border-color: var(--aa-bad) !important; color: #fff !important;
}
div[class*="st-key-manual_fail_"] button:hover { background: var(--aa-bad-strong) !important; border-color: var(--aa-bad-strong) !important; }
div[class*="st-key-tc-step-"] { background: rgba(var(--aa-fg-rgb),.035); }
div[class*="st-key-tc-card-"] button[kind="tertiary"] {
    padding: 0 .25rem;
    min-height: 1.9rem;
}
@container (max-width: 980px) {
    .st-key-test-case-toolbar [data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
        gap: .45rem !important;
    }
    .st-key-test-case-toolbar [data-testid="column"] { width: auto !important; min-width: 0; }
}
@container (max-width: 820px) {
    .st-key-test-cases-workspace [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        row-gap: .55rem;
    }
    .st-key-test-cases-workspace [data-testid="column"] {
        min-width: 145px;
    }
}
@container (max-width: 520px) {
    .st-key-test-case-quick-actions [data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: 1fr;
        gap: .4rem !important;
    }
    .st-key-test-case-quick-actions [data-testid="column"] { width: auto !important; min-width: 0; }
}
@container (max-width: 680px) {
    .st-key-test-run-manager [data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
        gap: .45rem !important;
    }
    .st-key-test-run-manager [data-testid="column"] { width: auto !important; min-width: 0; }
}
@container (max-width: 680px) {
    div[class*="st-key-tc-card-"] [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        row-gap: .45rem;
    }
    div[class*="st-key-tc-card-"] [data-testid="column"] { min-width: 0; }
}
</style>
"""

TEST_CASES_TOPBAR_CSS = """
<style>
.st-key-test-cases-topbar {
    padding-bottom: .7rem;
    border-bottom: 1px solid var(--aa-border);
    margin-bottom: .9rem;
}
.st-key-test-cases-topbar [data-testid="stHorizontalBlock"] { align-items: center; }
.st-key-test-cases-topbar h3 {
    margin: 0 !important; font-size: 1.35rem; letter-spacing: -.02em;
}
.st-key-test-cases-topbar .stCaption p { margin-bottom: 0; font-size: .82rem; }
.st-key-add-manual-test-action [data-testid="stPopover"] > button {
    background: var(--aa-accent) !important;
    color: #fff !important;
    border: 1px solid var(--aa-accent) !important;
    font-weight: 650;
    min-height: 2.5rem;
    box-shadow: 0 2px 10px rgba(var(--aa-accent-rgb),.22);
    transition: box-shadow .15s ease, transform .08s ease;
}
.st-key-add-manual-test-action [data-testid="stPopover"] > button:hover {
    box-shadow: 0 3px 16px rgba(var(--aa-accent-rgb),.32);
    transform: translateY(-1px);
}
.st-key-add-manual-test-action [data-testid="stPopover"] > button:active { transform: translateY(0); }
.st-key-add-manual-test-action [data-testid="stPopover"] > button p,
.st-key-add-manual-test-action [data-testid="stPopover"] > button span,
.st-key-add-manual-test-action [data-testid="stPopover"] > button svg {
    color: #fff !important; fill: #fff !important;
}
.st-key-reusable-runs-action [data-testid="stPopover"] > button {
    font-weight: 600; min-height: 2.5rem;
    transition: box-shadow .15s ease, transform .08s ease, border-color .15s ease;
}
.st-key-reusable-runs-action [data-testid="stPopover"] > button:hover {
    border-color: var(--aa-accent) !important; transform: translateY(-1px);
}
.aa-popover-section {
    font-size: .68rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .07em; color: var(--aa-accent); margin: .35rem 0 .1rem;
    opacity: .92;
}
.aa-popover-hint {
    font-size: .78rem; color: rgba(var(--aa-fg-rgb),.95);
    margin: -.15rem 0 .45rem; line-height: 1.35;
}
@container (max-width: 980px) {
    .st-key-test-cases-topbar [data-testid="stHorizontalBlock"] {
        display: grid !important; grid-template-columns: minmax(0, 1fr) auto auto;
        gap: .45rem !important;
    }
    .st-key-test-cases-topbar [data-testid="column"] { width: auto !important; min-width: 0; }
}
@container (max-width: 620px) {
    .st-key-test-cases-topbar [data-testid="stHorizontalBlock"] {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .st-key-test-cases-topbar [data-testid="column"]:first-child { grid-column: 1 / -1; }
    .st-key-test-cases-topbar [data-testid="stPopover"] > button { width: 100%; }
}
@media (prefers-reduced-motion: reduce) {
    .st-key-test-cases-topbar button { transition: none !important; }
}
</style>
"""
