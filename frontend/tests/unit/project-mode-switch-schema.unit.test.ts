import { describe, expect, it } from 'vitest';

import { projectModeSwitchResponseSchema } from '@/app/schemas/api';

describe('projectModeSwitchResponseSchema', () => {
  it('parses mode switch response payload', () => {
    const parsed = projectModeSwitchResponseSchema.parse({
      project_id: 101,
      previous_mode: 'audiobook',
      selected_mode: 'author',
      chapter_count: 12,
      reused_ingested_corpus: true,
    });

    expect(parsed.selected_mode).toBe('author');
    expect(parsed.reused_ingested_corpus).toBe(true);
  });
});
