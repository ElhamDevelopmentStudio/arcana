from app.services.normalization import normalize_text_with_warnings, repair_quote_mismatch


def test_unit_repair_quote_mismatch_normalizes_curly_open_quote_as_missing_close() -> None:
    repaired = repair_quote_mismatch('“Hello and took the map')

    assert repaired == '"Hello and took the map"'


def test_unit_normalize_text_with_warnings_normalizes_curly_mismatch_and_emits_low_confidence() -> None:
    repaired, warnings = normalize_text_with_warnings('He said “Hello and waited.', source='txt')

    assert repaired == 'He said "Hello and waited."'
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning['type'] == 'quote_repair_confidence_low'
    assert warning['source'] == 'txt'
    assert warning['action_count'] == 1
