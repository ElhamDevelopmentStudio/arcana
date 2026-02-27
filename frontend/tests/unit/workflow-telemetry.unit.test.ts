import { describe, expect, it } from 'vitest';

import {
  buildWorkflowTelemetryPayload,
  reportWorkflowTelemetry,
  WORKFLOW_TELEMETRY_EVENT_NAME,
} from '@/features/workflow/telemetry/workflow-telemetry';

function trackTelemetryEvents() {
  const payloads: unknown[] = [];
  const listener = (event: Event) => {
    payloads.push((event as CustomEvent).detail);
  };
  window.addEventListener(WORKFLOW_TELEMETRY_EVENT_NAME, listener as EventListener);
  return {
    payloads,
    cleanup() {
      window.removeEventListener(WORKFLOW_TELEMETRY_EVENT_NAME, listener as EventListener);
    },
  };
}

describe('workflow telemetry', () => {
  it('builds telemetry payload for mutating workflow actions', () => {
    const payload = buildWorkflowTelemetryPayload({
      method: 'post',
      path: '/api/projects/691/ingest/txt?dry_run=false',
      success: true,
      statusCode: 200,
    });

    expect(payload).toMatchObject({
      action: 'post_api_projects_:id_ingest_txt',
      method: 'POST',
      path: '/api/projects/:id/ingest/txt',
      status: 'success',
      status_code: 200,
      error_message: null,
    });
  });

  it('returns null for non-mutating requests', () => {
    expect(
      buildWorkflowTelemetryPayload({
        method: 'GET',
        path: '/api/projects/691/setup-status',
        success: true,
        statusCode: 200,
      }),
    ).toBeNull();
  });

  it('dispatches workflow telemetry event for failures with error message', () => {
    const tracked = trackTelemetryEvents();

    const payload = reportWorkflowTelemetry({
      method: 'PUT',
      path: '/api/projects/691/mode',
      success: false,
      statusCode: 500,
      errorMessage: 'Backend failed',
    });

    tracked.cleanup();

    expect(payload).toMatchObject({
      action: 'put_api_projects_:id_mode',
      status: 'failure',
      status_code: 500,
      error_message: 'Backend failed',
    });
    expect(tracked.payloads).toHaveLength(1);
  });
});
