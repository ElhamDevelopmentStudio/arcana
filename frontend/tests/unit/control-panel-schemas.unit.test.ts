import { describe, expect, it } from 'vitest';

import {
  healthSchema,
  projectControlPanelProjectListResponseSchema,
  projectControlPanelSummaryResponseSchema,
} from '@/app/schemas/api';

describe('control panel schemas', () => {
  it('parses health payload', () => {
    const parsed = healthSchema.parse({ status: 'ok' });
    expect(parsed.status).toBe('ok');
  });

  it('parses project control panel summary payload', () => {
    const parsed = projectControlPanelSummaryResponseSchema.parse({
      schema_version: '1.0.0',
      output_schema: 'project_control_panel_summary_json',
      output_format: 'json',
      output_id: 'CP-001',
      output_name: 'project_control_panel_summary',
      generated_at: '2026-02-27T00:00:00Z',
      generated_by: 'build_project_control_panel_summary',
      total_projects: 10,
      project_counts_by_state: [
        { lifecycle_state: 'draft', project_count: 2 },
        { lifecycle_state: 'ingested', project_count: 1 },
        { lifecycle_state: 'configured', project_count: 1 },
        { lifecycle_state: 'running', project_count: 1 },
        { lifecycle_state: 'completed', project_count: 3 },
        { lifecycle_state: 'failed', project_count: 1 },
        { lifecycle_state: 'archived', project_count: 1 },
      ],
      active_run_count: 1,
      blocked_export_project_count: 3,
      blocked_export_run_count: 2,
      recent_failure_count: 1,
      recent_failures: [],
    });

    expect(parsed.total_projects).toBe(10);
    expect(parsed.project_counts_by_state.find((item) => item.lifecycle_state === 'completed')?.project_count).toBe(3);
  });

  it('parses project control panel project-list payload', () => {
    const parsed = projectControlPanelProjectListResponseSchema.parse({
      schema_version: '1.0.0',
      output_schema: 'project_control_panel_project_list_json',
      output_format: 'json',
      output_id: 'CP-002',
      output_name: 'project_control_panel_project_list',
      generated_at: '2026-02-27T00:00:00Z',
      generated_by: 'build_project_control_panel_project_list',
      total_items: 1,
      page: 1,
      page_size: 20,
      has_next_page: false,
      items: [
        {
          project_id: 101,
          status: 'draft',
          selected_mode: 'audiobook',
          last_run_status: null,
          updated_at: '2026-02-27T00:00:00Z',
          next_required_action: 'ingest',
        },
      ],
    });

    expect(parsed.items[0].project_id).toBe(101);
    expect(parsed.items[0].next_required_action).toBe('ingest');
  });
});

