import { describe, expect, it } from 'vitest';
import { z } from 'zod';

import { runDetailSchema, runResponseSchema } from '@/app/schemas/api';

const ALLOWED_RUN_STATUSES = ['queued', 'running', 'completed', 'failed', 'cancelled'] as const;

describe('run status schemas', () => {
  it('accepts all defined run lifecycle statuses', () => {
    for (const status of ALLOWED_RUN_STATUSES) {
      const runResponse = runResponseSchema.parse({
        run_id: 1,
        project_id: 1,
        status,
        segment_count: 0,
      });
      expect(runResponse.status).toBe(status);

      const runDetail = runDetailSchema.parse({
        run_id: 1,
        project_id: 1,
        status,
        config: { mode: 'author' },
        changelog_entries: [],
        started_at: new Date().toISOString(),
        finished_at: null,
        segment_count: 0,
        llm_calls: [],
        llm_cache_metrics: {},
      });
      expect(runDetail.status).toBe(status);
    }
  });

  it('rejects unknown run status values', () => {
    expect(() =>
      runResponseSchema.parse({
        run_id: 1,
        project_id: 1,
        status: 'interrupted',
        segment_count: 0,
      }),
    ).toThrow(z.ZodError);
  });
});

