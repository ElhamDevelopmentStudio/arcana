import { describe, expect, it } from 'vitest';

import {
  characterExtractionJobStartSchema,
  characterExtractionJobStatusSchema,
  projectIngestionJobStartSchema,
  projectIngestionJobStatusSchema,
} from '@/app/schemas/api';

describe('job datetime schemas', () => {
  it('accepts timezone offsets for character extraction job payloads', () => {
    const start = characterExtractionJobStartSchema.parse({
      project_id: 5,
      job_id: '6e7f3a476ca44d168d617d4e2a70405e',
      status: 'queued',
      executor_name: 'thread',
      task_id: null,
      created_at: '2026-03-01T12:57:36.208714+04:30',
    });
    expect(start.created_at).toBe('2026-03-01T12:57:36.208714+04:30');

    const status = characterExtractionJobStatusSchema.parse({
      project_id: 5,
      job_id: '6e7f3a476ca44d168d617d4e2a70405e',
      status: 'running',
      progress: 25,
      message: 'Extracting',
      executor_name: 'thread',
      task_id: null,
      error_message: null,
      result: null,
      created_at: '2026-03-01T12:57:36.208714+04:30',
      started_at: '2026-03-01T12:57:37.208714+04:30',
      finished_at: null,
      updated_at: '2026-03-01T12:58:00.208714+04:30',
    });
    expect(status.created_at).toBe('2026-03-01T12:57:36.208714+04:30');
  });

  it('accepts timezone offsets for project ingestion job payloads', () => {
    const start = projectIngestionJobStartSchema.parse({
      project_id: 5,
      source: 'txt',
      job_id: 'a6f8d52b0d7f4e88a6cf783f8ebf8f2f',
      status: 'queued',
      executor_name: 'thread',
      task_id: null,
      created_at: '2026-03-01T13:10:00.000000+04:30',
    });
    expect(start.source).toBe('txt');

    const status = projectIngestionJobStatusSchema.parse({
      project_id: 5,
      source: 'txt',
      job_id: 'a6f8d52b0d7f4e88a6cf783f8ebf8f2f',
      status: 'completed',
      progress: 100,
      message: 'Done',
      executor_name: 'thread',
      task_id: null,
      error_message: null,
      result: {
        project_id: 5,
        chapter_count: 10,
        warnings: [],
        normalization_report: {},
      },
      created_at: '2026-03-01T13:10:00.000000+04:30',
      started_at: '2026-03-01T13:10:01.000000+04:30',
      finished_at: '2026-03-01T13:10:08.000000+04:30',
      updated_at: '2026-03-01T13:10:08.000000+04:30',
    });
    expect(status.progress).toBe(100);
  });
});
