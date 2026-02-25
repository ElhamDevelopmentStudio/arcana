import os

os.environ["DATABASE_URL"] = "sqlite:///./test_nipe_norm_em_dash_unit.db"

from app.services.normalization import normalize_em_dash_dialogue_style


def test_unit_normalize_em_dash_dialogue_leader_to_dialogue_hyphen_prefix_with_indent() -> None:
    raw = "\t —  The lantern dimmed.\n  —\u00A0 \"Hold on.\"\n\u2003—\tFinally."

    normalized = normalize_em_dash_dialogue_style(raw)

    assert normalized == "- The lantern dimmed.\n- \"Hold on.\"\n- Finally."


def test_unit_normalize_em_dash_dialogue_style_preserves_internal_em_dash_usage() -> None:
    raw = "He paused—thinking deeper."

    assert normalize_em_dash_dialogue_style(raw) == raw
