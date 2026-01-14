import { describe, expect, it } from 'vitest';

import { modeCatalogSchema } from '@/app/schemas/api';

const VALID_MODE_CATALOG = {
    modes: ['audiobook', 'academic', 'author', 'custom'],
    default_mode: 'audiobook',
    persisted_in: ['projects.selected_mode', 'runs.config_json.mode'],
    mode_profiles: {
      audiobook: {
        max_segment_chars: 120,
        export_formats: ['json', 'csv', 'time_series_json', 'graph_json'],
        export_chunk_size: 500,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        llm_confidence_threshold: 0.6,
        speaker_confidence_threshold: 0.6,
        high_ambiguity_dialogue_flag_threshold: 2,
        unstable_emotion_shift_transition_threshold: 4,
        unstable_emotion_shift_density_threshold: 0.5,
        deterministic_mode: false,
        deep_semantic_refinement: false,
        web_scraping_enabled: false,
        contradiction_review_required: true,
        profile_intent: 'tts-ready segmentation and stable narration defaults',
      },
      academic: {
        max_segment_chars: 220,
        export_formats: ['json', 'csv', 'time_series_json', 'graph_json'],
        export_chunk_size: 500,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        llm_confidence_threshold: 0.6,
        speaker_confidence_threshold: 0.6,
        high_ambiguity_dialogue_flag_threshold: 2,
        unstable_emotion_shift_transition_threshold: 4,
        unstable_emotion_shift_density_threshold: 0.5,
        deterministic_mode: false,
        deep_semantic_refinement: false,
        web_scraping_enabled: false,
        contradiction_review_required: true,
        profile_intent: 'longer analytical segments for metric-friendly aggregation',
      },
      author: {
        max_segment_chars: 160,
        export_formats: ['json', 'csv', 'time_series_json', 'graph_json'],
        export_chunk_size: 500,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        llm_confidence_threshold: 0.6,
        speaker_confidence_threshold: 0.6,
        high_ambiguity_dialogue_flag_threshold: 2,
        unstable_emotion_shift_transition_threshold: 4,
        unstable_emotion_shift_density_threshold: 0.5,
        deterministic_mode: false,
        deep_semantic_refinement: false,
        web_scraping_enabled: false,
        contradiction_review_required: true,
        profile_intent: 'balanced segmentation for narrative-health diagnostics',
      },
      custom: {
        max_segment_chars: 255,
        export_formats: ['json', 'csv', 'time_series_json', 'graph_json'],
        export_chunk_size: 500,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        llm_confidence_threshold: 0.6,
        speaker_confidence_threshold: 0.6,
        high_ambiguity_dialogue_flag_threshold: 2,
        unstable_emotion_shift_transition_threshold: 4,
        unstable_emotion_shift_density_threshold: 0.5,
        deterministic_mode: false,
        deep_semantic_refinement: false,
        web_scraping_enabled: false,
        contradiction_review_required: true,
        profile_intent: 'user-tuned baseline with conservative defaults',
      },
  },
};

describe('mode catalog schema', () => {
  it('accepts mode profile objects for all modes', () => {
    const parsed = modeCatalogSchema.parse(VALID_MODE_CATALOG);
    expect(parsed.mode_profiles.author.max_segment_chars).toBe(160);
    expect(parsed.mode_profiles.academic.provider_name).toBe('openrouter');
    expect(parsed.mode_profiles.audiobook.export_formats).toEqual([
      'json',
      'csv',
      'time_series_json',
      'graph_json',
    ]);
    expect(parsed.mode_profiles.audiobook.export_chunk_size).toBe(500);
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
