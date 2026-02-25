from __future__ import annotations

from datetime import datetime, timezone

from app.models import Run


def _mark_runs_stale(runs: list[Run], *, stale_reason: str, stale_detail: str | None = None) -> int:
    stale_marked = 0
    stale_marked_at = datetime.now(timezone.utc).isoformat()

    for run in runs:
        config = dict(run.config_json or {})

        if not config.get("artifacts_stale", False):
            stale_marked += 1

        config["artifacts_stale"] = True
        config["stale_reason"] = stale_reason
        config["stale_marked_at"] = stale_marked_at
        if stale_detail is not None:
            config["stale_detail"] = stale_detail
        run.config_json = config

    return stale_marked


def mark_runs_stale_for_mode_switch(runs: list[Run], selected_mode: str) -> int:
    stale_runs = [
        run
        for run in runs
        if (run_mode := str(dict(run.config_json or {}).get("mode", "")).strip().lower())
        and run_mode != selected_mode
    ]
    stale_marked = _mark_runs_stale(stale_runs, stale_reason="mode_switched", stale_detail=f"mode={selected_mode}")

    for run in stale_runs:
        config = dict(run.config_json or {})
        config["stale_on_mode"] = selected_mode
        run.config_json = config

    return stale_marked


def mark_runs_stale_for_gender_edit(runs: list[Run]) -> int:
    return _mark_runs_stale(
        runs,
        stale_reason="character_gender_edited",
        stale_detail="gender_fields_updated",
    )
