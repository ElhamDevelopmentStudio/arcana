import { describe, expect, it } from 'vitest';

import { runDetailSchema } from '@/app/schemas/api';

describe('runDetailSchema', () => {
  it('accepts config payloads that include mode_profile_snapshot', () => {
    const parsed = runDetailSchema.parse({
      run_id: 17,
      project_id: 3,
      status: 'completed',
      config: {
        mode: 'academic',
        max_segment_chars: 220,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        mode_profile_snapshot: {
          max_segment_chars: 220,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          profile_intent: 'longer analytical segments for metric-friendly aggregation',
        },
      },
      started_at: '2026-02-25T00:00:00Z',
      finished_at: '2026-02-25T00:01:00Z',
      segment_count: 12,
      llm_calls: [],
    });

    expect(parsed.config.mode).toBe('academic');
    expect((parsed.config.mode_profile_snapshot as Record<string, unknown>).profile_intent).toBe(
      'longer analytical segments for metric-friendly aggregation',
    );
  });
});
