"""Base styles: Streamlit chrome cleanup, layout shell, shared surfaces."""

GLOBAL_CSS = """
<style>

.block-container { padding-top: 1.5rem !important; padding-bottom: 3rem !important; max-width: 1500px; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { border-right: 1px solid var(--aa-border); }
[data-testid="stSidebar"] > div:first-child { padding-top: .85rem; }
h1, h2, h3 { letter-spacing: -.02em; }
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    border-radius: var(--aa-radius-sm) !important;
    font-weight: 550;
    transition: transform .06s ease, background .15s ease;
}
.stButton > button:active { transform: translateY(1px); }
.stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div {
    border-radius: var(--aa-radius-sm) !important;
}
div[data-baseweb="tab-list"] { gap: .35rem; border-bottom: 1px solid var(--aa-border); }
button[data-baseweb="tab"] { border-radius: var(--aa-radius-sm) var(--aa-radius-sm) 0 0; }
div[data-testid="stExpander"] details { border-radius: var(--aa-radius) !important; }
.aa-hero { display:flex; align-items:center; gap:.8rem; margin:.1rem 0 .35rem; }
.aa-hero-mark {
    width:36px; height:36px; border-radius:10px; background:var(--aa-accent-soft);
    color:var(--aa-accent); display:flex; align-items:center; justify-content:center;
    font-weight:800; font-size:.95rem;
}
.aa-hero-title { font-size:1.45rem; font-weight:700; letter-spacing:-.02em; line-height:1.1; }
.aa-hero-sub { color:rgba(var(--aa-fg-rgb),.95); font-size:.85rem; margin-top:.12rem; }
.aa-stats { display:grid; grid-template-columns:repeat(3,1fr); gap:.45rem; margin:.35rem 0 .15rem; }
.aa-stats > div { background:var(--aa-surface); border:1px solid var(--aa-border); border-radius:10px; padding:.5rem .35rem; text-align:center; }
.aa-stats span { display:block; font-size:1.15rem; font-weight:700; line-height:1.15; }
.aa-stats label { font-size:.63rem; text-transform:uppercase; letter-spacing:.05em; opacity:.68; }
.aa-empty { border:1px dashed var(--aa-border-strong); border-radius:var(--aa-radius); padding:1.4rem 1rem; text-align:center; background:var(--aa-surface); }
.aa-empty-title { font-weight:650; }
.aa-empty-body { color:rgba(var(--aa-fg-rgb),.95); font-size:.88rem; margin-top:.25rem; }
.aa-inner-divider { margin:.7rem 0 .35rem; padding-top:.45rem; border-top:1px dashed var(--aa-border); font-size:.7rem; text-transform:uppercase; letter-spacing:.07em; opacity:.65; text-align:center; }
</style>
"""
