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
});
