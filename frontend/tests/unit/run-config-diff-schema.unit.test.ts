import { describe, expect, it } from 'vitest';

import { runConfigDiffResponseSchema } from '@/app/schemas/api';

describe('runConfigDiffResponseSchema', () => {
  it('accepts valid run config diff payloads', () => {
    const parsed = runConfigDiffResponseSchema.parse({
      project_id: 14,
      base_run_id: 91,
      target_run_id: 92,
      base_config_schema_version: '1.0.0',
      target_config_schema_version: '1.0.0',
      is_identical: false,
      changed_fields: [
        {
          field: 'mode',
          base_value: 'author',
          target_value: 'academic',
        },
      ],
      base_only_fields: [],
      target_only_fields: ['deterministic_seed'],
    });

    expect(parsed.changed_fields[0].field).toBe('mode');
    expect(parsed.target_only_fields).toContain('deterministic_seed');
  });

  it('rejects payloads with invalid run ids', () => {
    expect(() =>
      runConfigDiffResponseSchema.parse({
        project_id: 14,
        base_run_id: 0,
        target_run_id: 92,
        base_config_schema_version: '1.0.0',
        target_config_schema_version: '1.0.0',
        is_identical: true,
        changed_fields: [],
        base_only_fields: [],
        target_only_fields: [],
      }),
    ).toThrow();
  });
});
