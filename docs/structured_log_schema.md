# Structured Log Schema

Arcana services emit structured JSON logs through `app.services.structured_logging`.

## Canonical fields

- `schema_version`: schema version string (currently `1.0`)
- `timestamp`: UTC timestamp in ISO-8601 format
- `level`: one of `debug`, `info`, `warning`, `error`, `critical`
- `service`: logical service name (`run_orchestration`, `pipeline_execution`, `background_jobs`, etc.)
- `event`: stable event identifier
- `message`: human-readable event summary
- `metadata`: free-form object for event-specific context
- `project_id` (optional): related project id
- `run_id` (optional): related run id
- `correlation_id` (optional): request/job correlation id

## Example

```json
{
  "schema_version": "1.0",
  "timestamp": "2026-02-26T17:03:52.941302Z",
  "level": "info",
  "service": "run_orchestration",
  "event": "run_execution_dispatched",
  "message": "Run execution dispatched",
  "project_id": 12,
  "run_id": 48,
  "metadata": {
    "mode": "AO-001",
    "recovery": false
  }
}
```
