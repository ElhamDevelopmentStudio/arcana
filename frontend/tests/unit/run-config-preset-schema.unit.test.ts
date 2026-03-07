import { describe, expect, it } from 'vitest';

import { runConfigPresetResponseSchema } from '@/app/schemas/api';

describe('runConfigPresetResponseSchema', () => {
  it('accepts exported run preset payloads', () => {
    const parsed = runConfigPresetResponseSchema.parse({
      project_id: 31,
      run_id: 44,
      preset_schema_version: '1.0.0',
      generated_at: '2026-02-26T20:00:00Z',
      run_config: {
        mode: 'author',
        max_segment_chars: 180,
        export_formats: ['json', 'csv'],
        deterministic_mode: true,
      },
    });

    expect(parsed.run_config.mode).toBe('author');
    expect(parsed.run_config.export_formats).toEqual(['json', 'csv']);
  });

  it('rejects invalid preset payloads', () => {
    expect(() =>
      runConfigPresetResponseSchema.parse({
        project_id: 31,
        run_id: 44,
        preset_schema_version: '1.0.0',
        generated_at: '2026-02-26T20:00:00Z',
        run_config: {
          mode: 'author',
          export_formats: ['invalid_format'],
        },
      }),
    ).toThrow();
  });
});
