# Quick Onboarding Seed Fixtures

This folder provides a minimal, deterministic seed dataset for first-run local onboarding:

- `minimal-novel.txt`: 2-chapter TXT ingestion sample
- `characters-minimal.json`: small character map import sample
- `run-request.json`: baseline run payload for a local export

Recommended flow:
1. Create project
2. Ingest `minimal-novel.txt`
3. Import `characters-minimal.json`
4. Create run with `run-request.json`
5. Export `GET /api/projects/{project_id}/exports/{run_id}.json`
