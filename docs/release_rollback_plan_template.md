# Release Rollback Plan Template

Use this template for any release where database, API, export, or routing behavior may require controlled rollback.

## Rollback Plan Template

### Section 1: Release identification and blast radius
- objective: Record the exact release artifact, deployment window, owners, and impacted systems.
- required_inputs: release version/commit, environment list, service owners, user-facing risk summary.
- completion_criteria: Rollback operators can identify scope and stakeholder contacts without additional context.

### Section 2: Rollback triggers and decision thresholds
- objective: Define measurable conditions that require rollback rather than forward-fix.
- required_inputs: error-rate thresholds, latency/SLO breaches, data-integrity signals, time-bound decision window.
- completion_criteria: Go/no-go rollback decision can be made from objective telemetry within the declared timeframe.

### Section 3: Pre-rollback safeguards and backups
- objective: Ensure backup/checkpoint state exists and can be restored before mutating production state.
- required_inputs: backup identifiers, snapshot timestamps, restore validation owner, dependency freeze list.
- completion_criteria: Required restore points are verified and signed off before executing rollback commands.

### Section 4: Step-by-step rollback execution commands
- objective: Provide ordered, copy-ready rollback steps for app deploys, migrations, and configuration toggles.
- required_inputs: command sequence, migration reversal strategy, feature-flag state targets, verification pauses.
- completion_criteria: Operators can execute rollback deterministically using numbered steps without improvisation.

### Section 5: Post-rollback verification checklist
- objective: Confirm system health, data consistency, and contract behavior after rollback.
- required_inputs: health endpoint checks, key query checks, export/contract smoke checks, dashboard verification links.
- completion_criteria: Verification evidence shows the system returned to an accepted baseline state.

### Section 6: Incident log, communications, and follow-up actions
- objective: Capture timeline, decisions, communications, and required corrective actions after rollback.
- required_inputs: incident timeline, stakeholder notification log, root-cause hypothesis, follow-up task IDs.
- completion_criteria: Incident record is complete and actionable follow-ups are assigned with owners/dates.
