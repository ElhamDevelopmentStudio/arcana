from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_TEMPLATE_PATH = ROOT / "docs" / "final_acceptance_report_template.md"

EXPECTED_CRITERIA = [
    ("AC-001", "A Shadow Slave corpus can be ingested and chapterized correctly."),
    ("AC-002", "Character map can be created/edited with fields: name, verbalized form, gender."),
    ("AC-003", "Pronunciation substitutions appear in preview and export correctly."),
    (
        "AC-004",
        "Export produces ordered segments with phonetic-ready text, speaker/gender/voice tags "
        "(where applicable), and emotion tags plus confidence.",
    ),
    ("AC-005", "Contradictory gender results are flagged for review."),
    ("AC-006", "Outputs are reproducible when configuration and inputs are unchanged."),
    ("AC-007", "Incremental addition of chapters updates outputs without reprocessing everything."),
]


def test_integration_final_acceptance_report_template_contains_all_criteria() -> None:
    markdown = REPORT_TEMPLATE_PATH.read_text(encoding="utf-8")

    for criterion_id, criterion_text in EXPECTED_CRITERIA:
        criterion_line = f"- {criterion_id}: {criterion_text}"
        status_line = "  Status: PASS | FAIL"
        assert criterion_line in markdown
        criterion_block_start = markdown.index(criterion_line)
        status_pos = markdown.find(status_line, criterion_block_start)
        assert status_pos != -1


def test_regression_final_acceptance_report_template_criterion_count() -> None:
    markdown = REPORT_TEMPLATE_PATH.read_text(encoding="utf-8")

    criterion_ids = [line.split(":")[0].removeprefix("- ").strip() for line in markdown.splitlines() if line.startswith("- AC-")]
    assert criterion_ids == [criterion_id for criterion_id, _ in EXPECTED_CRITERIA]

    pass_fail_lines = [line.strip() for line in markdown.splitlines() if line.strip() == "Status: PASS | FAIL"]
    assert len(pass_fail_lines) == len(EXPECTED_CRITERIA)

