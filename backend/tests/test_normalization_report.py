from app.services.normalization import (
    build_normalization_report,
    normalize_text_with_report,
)


def test_unit_normalize_text_with_report_emits_quote_repair_metrics() -> None:
    normalized, warnings, report = normalize_text_with_report('He said "Hello and waited.', source="txt")

    assert normalized == 'He said "Hello and waited."'
    assert any(warning["type"] == "quote_repair_confidence_low" for warning in warnings)
    assert report["counts"]["quote_repair_count"] == 1
    assert report["counts"]["copy_artifact_removed_lines"] == 0
    assert report["lossy_transform_flags"]["quote_repair_applied"] is True


def test_unit_build_normalization_report_aggregates_counts_and_flags() -> None:
    _, _, chapter_report_1 = normalize_text_with_report("This has a non\u00a0breaking space.", source="txt")
    _, _, chapter_report_2 = normalize_text_with_report('He said "Open quote here', source="txt")

    report = build_normalization_report(
        source="txt",
        chapter_count=2,
        chapter_reports=[chapter_report_1, chapter_report_2],
        suspected_duplicate_title_count=1,
        encoding_issue_count=2,
    )

    assert report["counts"]["chapters_detected"] == 2
    assert report["counts"]["suspected_duplicates"] == 1
    assert report["counts"]["suspected_duplicate_content"] == 0
    assert report["counts"]["quote_repair_count"] == 1
    assert report["counts"]["encoding_issues"] == 2
    assert report["lossy_transform_flags"]["unicode_normalization"] is True
    assert report["lossy_transform_flags"]["quote_repair_applied"] is True
