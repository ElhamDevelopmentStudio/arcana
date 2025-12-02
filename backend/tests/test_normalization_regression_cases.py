from app.services.normalization import normalize_text_with_warnings


def test_regression_ocr_like_input_normalizes_to_stable_text() -> None:
    text = (
        "Chapter 1\u2028"
        "The\u00a0captain said,\t“Hold on…”\r\n"
        "Page 12\n"
        "He replied,\u00a0“Proceed.”\n"
    )
    normalized, warnings = normalize_text_with_warnings(text, source="txt")

    assert warnings == []
    assert (
        normalized
        == 'Chapter 1\nThe captain said, "Hold on..."\nHe replied, "Proceed."'
    )


def test_regression_quote_mismatch_edge_case_with_straightforward_contractions() -> None:
    normalized, warnings = normalize_text_with_warnings(
        'He told me “I’m late and can’t stay.',
        source="txt",
    )

    assert normalized == 'He told me "I\'m late and can\'t stay."'
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning["type"] == "quote_repair_confidence_low"
    assert warning["action_count"] == 1
