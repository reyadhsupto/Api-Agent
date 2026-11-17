# tests/test_theme_tokens.py

"""Guards for the frontend design system."""

import importlib
import pathlib
import re

from frontend.styles import tokens

STYLE_DIR = pathlib.Path(tokens.__file__).resolve().parent
CJK = re.compile(r"[\u2e80-\u9fff\uac00-\ud7af\uff00-\uffef]")


def _stylesheets():
    """Yield the file name and CSS text of every stylesheet module."""
    for path in sorted(STYLE_DIR.glob("*.py")):
        module = importlib.import_module("frontend.styles." + path.stem)
        blocks = [
            value for value in vars(module).values()
            if isinstance(value, str) and "<style>" in value
        ]
        if blocks:
            yield path.name, "\n".join(blocks)


def test_palettes_declare_the_same_tokens():
    """Both palettes must expose identical token names."""
    assert set(tokens.DARK) == set(tokens.LIGHT)


def test_box_tokens_exist_in_both_palettes():
    """The box system depends on these tokens being declared."""
    required = {
        "aa-canvas", "aa-rail", "aa-panel", "aa-panel-alt", "aa-elevated",
        "aa-overlay", "aa-hover", "aa-active", "aa-line", "aa-line-soft",
        "aa-line-strong", "aa-line-contrast", "aa-line-accent", "aa-text",
        "aa-text-dim", "aa-text-mute", "aa-on-accent", "aa-box-fill",
        "aa-box-line", "aa-box-shadow", "aa-box-pad", "aa-chip-fill",
        "aa-chip-line", "aa-accent-soft", "aa-accent-wash",
    }
    for theme in ("dark", "light"):
        assert required <= set(tokens.palette(theme))


def test_dark_canvas_is_pure_black():
    """The dark workspace is black, not a grey surface."""
    assert tokens.DARK["aa-canvas"] == "#000000"


def test_edge_ladder_rises_above_black():
    """Each dark edge must out-rank the step below it to stay visible."""
    ladder = {"aa-line-soft": 0.14, "aa-line": 0.20,
              "aa-line-strong": 0.30, "aa-line-contrast": 0.40}
    for name, floor in ladder.items():
        alpha = float(tokens.DARK[name].split(",")[-1].strip(" )"))
        assert alpha >= floor, (name, alpha, floor)


def test_accent_ink_is_not_white():
    """White on the orange accent measures 2.8:1 and must not be used."""
    for theme in ("dark", "light"):
        assert tokens.palette(theme)["aa-on-accent"].lower() not in {"#fff", "#ffffff"}


def test_every_var_reference_resolves():
    """No stylesheet may reference an undeclared custom property."""
    defined = set(tokens.palette("dark")) | set(tokens.RADII) | set(tokens.MOTION) | set(tokens.FONTS)
    missing = [
        (name, reference)
        for name, css in _stylesheets()
        for reference in re.findall(r"var\(--(aa-[a-z0-9-]+)", css)
        if reference not in defined
    ]
    assert not missing, missing


def test_style_blocks_are_brace_balanced_and_ascii():
    """An unbalanced block voids the rules after it; a CJK glyph is invisible."""
    for name, css in _stylesheets():
        assert css.count("{") == css.count("}"), name
        assert not CJK.search(css), name
