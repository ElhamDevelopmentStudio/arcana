from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKLIST_PATH = ROOT / "SRS_Expanded_Implementation_Checklist.md"

EXPECTED_LABELLED_EXCLUDES = [
    "`[BACKLOG][MVP-EXCLUDED][NICE-TO-HAVE]` full motif recurrence modeling.",
    "`[BACKLOG][MVP-EXCLUDED][NICE-TO-HAVE]` advanced comparative clustering.",
    "`[BACKLOG][MVP-EXCLUDED][NICE-TO-HAVE]` community sentiment overlay.",
    "`[BACKLOG][MVP-EXCLUDED][NICE-TO-HAVE]` automatic web scraping by default.",
]


def test_integration_checklist_mvp_excludes_have_explicit_backlog_labels() -> None:
    checklist_markdown = CHECKLIST_PATH.read_text(encoding="utf-8")
    for labeled_item in EXPECTED_LABELLED_EXCLUDES:
        assert labeled_item in checklist_markdown
