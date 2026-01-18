import { describe, expect, it } from 'vitest';
import { z } from 'zod';

import { runRequestSchema } from '@/app/schemas/api';

describe('runRequestSchema', () => {
  it('includes warning threshold defaults', () => {
    const parsed = runRequestSchema.parse({
      mode: 'academic',
      max_segment_chars: 120,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
    });

    expect(parsed.web_scraping_enabled).toBe(false);
    expect(parsed.speaker_confidence_threshold).toBe(0.6);
    expect(parsed.high_ambiguity_dialogue_flag_threshold).toBe(2);
    expect(parsed.unstable_emotion_shift_transition_threshold).toBe(4);
    expect(parsed.unstable_emotion_shift_density_threshold).toBe(0.5);
    expect(parsed.contradiction_review_required).toBe(true);
  });

  it('allows explicit web scraping toggle overrides', () => {
    const parsed = runRequestSchema.parse({
      mode: 'academic',
      max_segment_chars: 120,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      web_scraping_enabled: true,
    });

    expect(parsed.web_scraping_enabled).toBe(true);
  });

  it('defaults emotion taxonomy to basic when not provided', () => {
    const parsed = runRequestSchema.parse({
      mode: 'academic',
      max_segment_chars: 120,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
    });

    expect(parsed.emotion_taxonomy).toBe('basic');
  });

  it('normalizes and deduplicates export formats', () => {
    const parsed = runRequestSchema.parse({
      mode: 'academic',
      max_segment_chars: 120,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      export_formats: [' CSV ', 'json', 'csv', 'time_series_json', 'GRAPH_JSON', 'CSV'],
    });

    expect(parsed.export_formats).toEqual(['csv', 'json', 'time_series_json', 'graph_json']);
  });

  it('accepts export chunk size in valid range', () => {
    const parsed = runRequestSchema.parse({
      mode: 'academic',
      max_segment_chars: 120,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      export_chunk_size: 250,
    });

    expect(parsed.export_chunk_size).toBe(250);
  });

  it('rejects export chunk size outside valid range', () => {
    expect(() =>
      runRequestSchema.parse({
        mode: 'academic',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        export_chunk_size: 0,
      }),
    ).toThrow(z.ZodError);
  });

  it('accepts deterministic mode config fields', () => {
    const parsed = runRequestSchema.parse({
      mode: 'academic',
      max_segment_chars: 120,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      deterministic_mode: true,
      deterministic_model_identifier: 'openai/gpt-4o-mini',
      deterministic_seed: 2026,
      randomization_config: {
        seed: 2026,
        strategy: 'stable',
        shuffle_enabled: false,
      },
    });

    expect(parsed.deterministic_mode).toBe(true);
    expect(parsed.deterministic_model_identifier).toBe('openai/gpt-4o-mini');
    expect(parsed.deterministic_seed).toBe(2026);
    expect(parsed.randomization_config).toEqual({
      seed: 2026,
      strategy: 'stable',
      shuffle_enabled: false,
    });
  });

  it('rejects negative deterministic seed', () => {
    expect(() =>
      runRequestSchema.parse({
        mode: 'academic',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        deterministic_mode: true,
        deterministic_seed: -1,
      }),
    ).toThrow(z.ZodError);
  });

  it('requires export formats when explicitly provided', () => {
    expect(() =>
      runRequestSchema.parse({
        mode: 'academic',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        export_formats: ['not_a_format'],
      }),
    ).toThrow(z.ZodError);
  });

  it('accepts expanded taxonomy for run requests', () => {
    const parsed = runRequestSchema.parse({
      mode: 'academic',
      max_segment_chars: 120,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      emotion_taxonomy: 'expanded',
    });

    expect(parsed.emotion_taxonomy).toBe('expanded');
  });

  it('rejects unsupported emotion taxonomy values', () => {
    expect(() =>
      runRequestSchema.parse({
        mode: 'academic',
        max_segment_chars: 120,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        emotion_taxonomy: 'ultra',
      }),
    ).toThrow(z.ZodError);
  });

  it('accepts custom warning threshold values', () => {
    const parsed = runRequestSchema.parse({
      mode: 'author',
      max_segment_chars: 160,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      speaker_confidence_threshold: 0.72,
      high_ambiguity_dialogue_flag_threshold: 3,
      unstable_emotion_shift_transition_threshold: 6,
      unstable_emotion_shift_density_threshold: 0.4,
    });

    expect(parsed.speaker_confidence_threshold).toBe(0.72);
    expect(parsed.high_ambiguity_dialogue_flag_threshold).toBe(3);
    expect(parsed.unstable_emotion_shift_transition_threshold).toBe(6);
    expect(parsed.unstable_emotion_shift_density_threshold).toBe(0.4);
    expect(parsed.contradiction_review_required).toBe(true);
  });

  it('accepts explicit contradiction_review_required false', () => {
    const parsed = runRequestSchema.parse({
      mode: 'academic',
      max_segment_chars: 120,
      llm_enabled: false,
      provider_name: 'openrouter',
      max_calls_per_day: 25,
      contradiction_review_required: false,
    });

    expect(parsed.contradiction_review_required).toBe(false);
  });

  it('validates warning thresholds are in expected ranges', () => {
    expect(() =>
      runRequestSchema.parse({
        mode: 'author',
        max_segment_chars: 160,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
        speaker_confidence_threshold: 1.2,
      }),
    ).toThrow(z.ZodError);
  });

  it('rejects max_segment_chars above 255', () => {
    expect(() =>
      runRequestSchema.parse({
        mode: 'author',
        max_segment_chars: 256,
        llm_enabled: false,
        provider_name: 'openrouter',
        max_calls_per_day: 25,
      }),
    ).toThrow(z.ZodError);
  });
});
