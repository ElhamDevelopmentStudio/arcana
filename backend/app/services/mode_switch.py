from __future__ import annotations

from datetime import datetime, timezone

from app.models import Run


def mark_runs_stale_for_mode_switch(runs: list[Run], selected_mode: str) -> int:
    stale_marked = 0
    stale_marked_at = datetime.now(timezone.utc).isoformat()

    for run in runs:
        config = dict(run.config_json or {})
        run_mode = str(config.get("mode", "")).strip().lower()

        if run_mode and run_mode != selected_mode:
            if not config.get("artifacts_stale", False):
                stale_marked += 1
            config["artifacts_stale"] = True
            config["stale_reason"] = "mode_switched"
            config["stale_on_mode"] = selected_mode
            config["stale_marked_at"] = stale_marked_at
            run.config_json = config

    return stale_marked
