import { describe, expect, it } from 'vitest';

import { runDetailSchema } from '@/app/schemas/api';

describe('runDetailSchema', () => {
  it('accepts non-empty llm_cache_metrics task records', () => {
    const parsed = runDetailSchema.parse({
      run_id: 956,
      project_id: 691,
      status: 'completed',
      config: {
        mode: 'audiobook',
        max_segment_chars: 120,
      },
      started_at: '2026-02-27T19:41:05Z',
      finished_at: '2026-02-27T19:41:07Z',
      segment_count: 53,
      llm_cache_metrics: {
        sentiment_probe: {
          hits: 0,
          misses: 1,
        },
      },
      llm_calls: [
        {
          id: 44,
          provider: 'openrouter',
          task_type: 'sentiment_probe',
          success: true,
          request_count: 1,
          is_cache_hit: false,
          detail: null,
          created_at: '2026-02-27T19:41:07Z',
        },
      ],
    });

    expect(parsed.llm_cache_metrics.sentiment_probe.hits).toBe(0);
    expect(parsed.llm_cache_metrics.sentiment_probe.misses).toBe(1);
  });

  it('accepts config payloads that include mode_profile_snapshot', () => {
    const parsed = runDetailSchema.parse({
      run_id: 17,
      project_id: 3,
      status: 'completed',
      config: {
        mode: 'academic',
        config_schema_version: '1.0.0',
        max_segment_chars: 220,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        mode_profile_snapshot: {
          max_segment_chars: 220,
          llm_enabled: false,
          provider_name: 'openrouter',
          max_calls_per_day: 25,
          llm_confidence_threshold: 0.6,
          deep_semantic_refinement: false,
          deterministic_mode: false,
          profile_intent: 'longer analytical segments for metric-friendly aggregation',
        },
      },
      started_at: '2026-02-25T00:00:00Z',
      finished_at: '2026-02-25T00:01:00Z',
      segment_count: 12,
      llm_calls: [],
    });

    expect(parsed.config.mode).toBe('academic');
    expect(parsed.config.config_schema_version).toBe('1.0.0');
    expect((parsed.config.mode_profile_snapshot as Record<string, unknown>).profile_intent).toBe(
      'longer analytical segments for metric-friendly aggregation',
    );
  });

  it('validates llm call task types against the supported enumeration', () => {
    const parsed = runDetailSchema.parse({
      run_id: 22,
      project_id: 3,
      status: 'completed',
      config: {
        mode: 'audiobook',
        max_segment_chars: 200,
      },
      started_at: '2026-02-25T00:00:00Z',
      finished_at: '2026-02-25T00:01:00Z',
      segment_count: 9,
      llm_calls: [
        {
          id: 1,
          provider: 'openrouter',
          task_type: 'emotion_refinement',
          success: true,
          request_count: 1,
          is_cache_hit: false,
          detail: null,
          created_at: '2026-02-25T00:00:01Z',
        },
      ],
    });

    expect(parsed.llm_calls[0].task_type).toBe('emotion_refinement');

    expect(() =>
      runDetailSchema.parse({
        run_id: 22,
        project_id: 3,
        status: 'completed',
        config: {
          mode: 'audiobook',
          max_segment_chars: 200,
        },
        started_at: '2026-02-25T00:00:00Z',
        finished_at: '2026-02-25T00:01:00Z',
        segment_count: 9,
        llm_calls: [
          {
            id: 2,
            provider: 'openrouter',
            task_type: 'unsupported_task',
            success: true,
            request_count: 1,
            is_cache_hit: false,
            detail: null,
            created_at: '2026-02-25T00:00:01Z',
          },
        ],
      }),
    ).toThrow();
  });

  it('accepts optional changelog entries', () => {
    const parsed = runDetailSchema.parse({
      run_id: 30,
      project_id: 3,
      status: 'completed',
      config: {
        mode: 'audiobook',
        max_segment_chars: 210,
      },
      changelog_entries: [
        {
          id: 1,
          event_type: 'run_created',
          event_message: 'Run record created',
          event_metadata: {
            mode: 'audiobook',
          },
          created_at: '2026-02-25T00:00:00Z',
        },
      ],
      started_at: '2026-02-25T00:00:00Z',
      finished_at: '2026-02-25T00:01:00Z',
      segment_count: 8,
      llm_calls: [
        {
          id: 1,
          provider: 'openrouter',
          task_type: 'emotion_refinement',
          success: true,
          request_count: 1,
          is_cache_hit: false,
          detail: null,
          created_at: '2026-02-25T00:00:01Z',
        },
      ],
    });

    expect(parsed.changelog_entries).toHaveLength(1);
    expect(parsed.changelog_entries[0].event_type).toBe('run_created');
  });
});
