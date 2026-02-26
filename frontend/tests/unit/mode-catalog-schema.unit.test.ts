import { describe, expect, it } from 'vitest';

import { modeCatalogSchema } from '@/app/schemas/api';

const VALID_MODE_CATALOG = {
  modes: ['audiobook', 'academic', 'author', 'custom'],
  default_mode: 'audiobook',
  persisted_in: ['projects.selected_mode', 'runs.config_json.mode'],
  mode_profiles: {
    audiobook: {
      max_segment_chars: 120,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      llm_confidence_threshold: 0.6,
      deterministic_mode: false,
      deep_semantic_refinement: false,
      profile_intent: 'tts-ready segmentation and stable narration defaults',
    },
    academic: {
      max_segment_chars: 220,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      llm_confidence_threshold: 0.6,
      deterministic_mode: false,
      deep_semantic_refinement: false,
      profile_intent: 'longer analytical segments for metric-friendly aggregation',
    },
    author: {
      max_segment_chars: 160,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      llm_confidence_threshold: 0.6,
      deterministic_mode: false,
      deep_semantic_refinement: false,
      profile_intent: 'balanced segmentation for narrative-health diagnostics',
    },
    custom: {
      max_segment_chars: 255,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      llm_confidence_threshold: 0.6,
      deterministic_mode: false,
      deep_semantic_refinement: false,
      profile_intent: 'user-tuned baseline with conservative defaults',
    },
  },
};

describe('mode catalog schema', () => {
  it('accepts mode profile objects for all modes', () => {
    const parsed = modeCatalogSchema.parse(VALID_MODE_CATALOG);
    expect(parsed.mode_profiles.author.max_segment_chars).toBe(160);
    expect(parsed.mode_profiles.academic.provider_name).toBe('openrouter');
  });

  it('rejects payloads without mode profile contract', () => {
    const invalidPayload = {
      modes: ['audiobook', 'academic', 'author', 'custom'],
      default_mode: 'audiobook',
      persisted_in: ['projects.selected_mode', 'runs.config_json.mode'],
    };
    expect(() => modeCatalogSchema.parse(invalidPayload)).toThrow();
  });
});
