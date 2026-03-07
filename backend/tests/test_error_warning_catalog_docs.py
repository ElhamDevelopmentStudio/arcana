from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "error_warning_catalog.md"
README_PATH = ROOT / "README.md"


EXPECTED_ERROR_TYPES = {
    "unsupported_format",
    "unsupported_encoding",
    "missing_chapters",
}

EXPECTED_WARNING_TYPES = {
    "ambiguous_alias_collision",
    "ambiguous_chapter_boundaries",
    "ambiguous_replacement",
    "chapter_title_dedup_action",
    "deterministic_replay_warning",
    "duplicate_canonical_candidates",
    "duplicate_chapter_title",
    "high_ambiguity_dialogue_block",
    "inferred_gender_insufficient_evidence",
    "low_confidence_character_candidate",
    "low_confidence_speaker_attribution",
    "manual_inferred_gender_contradiction",
    "quote_repair_confidence_low",
    "suspected_duplicate_content",
    "unstable_rapid_emotion_shift",
}


def test_unit_error_warning_catalog_has_required_sections() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    assert content.startswith("# Error & Warning Catalog")
    assert "## Error Catalog" in content
    assert "## Warning Catalog" in content
    assert "Operational note" in content


def test_unit_error_warning_catalog_covers_all_known_error_warning_codes() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    for error_type in EXPECTED_ERROR_TYPES:
        assert f"`{error_type}`" in content, f"Missing documented error type: {error_type}"
    for warning_type in EXPECTED_WARNING_TYPES:
        assert f"`{warning_type}`" in content, f"Missing documented warning type: {warning_type}"


def test_unit_readme_links_to_error_warning_catalog() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    assert "`docs/error_warning_catalog.md`" in readme
