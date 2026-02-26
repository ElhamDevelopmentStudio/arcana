from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.pr_template_frontend_impact_validation import (  # noqa: E402
    PRTemplateFrontendImpactValidationError,
    validate_pr_template_frontend_impact,
)


def main() -> int:
    template_path = ROOT / ".github" / "pull_request_template.md"

    try:
        stats = validate_pr_template_frontend_impact(template_path)
    except PRTemplateFrontendImpactValidationError as exc:
        print(f"PR template frontend-impact validation failed: {exc}")
        return 1

    print(
        "PR template frontend-impact validation succeeded with "
        f"{stats['required_entries']} required entries."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
