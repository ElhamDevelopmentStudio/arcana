import { describe, expect, it } from 'vitest';

import { projectModeSwitchResponseSchema } from '@/app/schemas/api';

describe('projectModeSwitchResponseSchema', () => {
  it('parses mode switch response payload', () => {
    const parsed = projectModeSwitchResponseSchema.parse({
      project_id: 101,
      previous_mode: 'audiobook',
      selected_mode: 'author',
      selected_modes: ['audiobook', 'author'],
      chapter_count: 12,
      reused_ingested_corpus: true,
      stale_runs_marked: 1,
    });

    expect(parsed.selected_mode).toBe('author');
    expect(parsed.selected_modes).toEqual(['audiobook', 'author']);
    expect(parsed.reused_ingested_corpus).toBe(true);
    expect(parsed.stale_runs_marked).toBe(1);
  });
});
