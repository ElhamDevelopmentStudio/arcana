import { describe, expect, it } from 'vitest';

import { polarityGraphResponseSchema } from '@/app/schemas/api';

const VALID_POLARITY_GRAPH_PAYLOAD = {
  metric_id: 'rolling_emotional_polarity',
  metric_label: 'Rolling emotional polarity',
  source_path: ['rolling_window_emotional_curves', 'valence_curve'],
  value_key: 'rolling_mean_valence',
  points: [
    {
      position: 1,
      rolling_mean_valence: -0.12,
      rolling_mean_intensity: 0.47,
      chapter_id: 1,
      segment_index: 1,
      segment_id: '1-001',
    },
    {
      position: 2,
      rolling_mean_valence: 0.08,
      rolling_mean_intensity: 0.55,
      chapter_id: 1,
      segment_index: 2,
      segment_id: '1-002',
    },
  ],
  volatility_markers: [
    {
      position: 2,
      from_segment_id: '1-001',
      segment_id: '1-002',
      chapter_id: 1,
      segment_index: 2,
      volatility_index: 0.26,
      level: 'moderate',
      valence_delta: 0.12,
      intensity_delta: 0.08,
      tension_delta: -0.01,
      dominance_delta: 0.1,
      triggers: ['emotion pivot', 'tone drift'],
      from_tension: 0.18,
      to_tension: 0.19,
    },
  ],
  metadata: {
    rolling_window_size: 5,
    volatility_markers_count: 1,
  },
};

describe('polarity graph schema', () => {
  it('accepts valid emotional polarity chart payload', () => {
    const parsed = polarityGraphResponseSchema.parse(VALID_POLARITY_GRAPH_PAYLOAD);

    expect(parsed.metric_id).toBe('rolling_emotional_polarity');
    expect(parsed.points).toHaveLength(2);
    expect(parsed.volatility_markers[0].level).toBe('moderate');
    expect(parsed.volatility_markers[0].position).toBe(2);
  });

  it('rejects payloads missing required polarity fields', () => {
    const invalidPayload = {
      ...VALID_POLARITY_GRAPH_PAYLOAD,
      metric_id: 123,
      value_key: null,
    };

    expect(() => polarityGraphResponseSchema.parse(invalidPayload)).toThrow();
  });
});
