import { describe, expect, it } from 'vitest';

import { characterMapItemSchema, characterMapSchema } from '@/app/schemas/api';

describe('character schema', () => {
  it('accepts allowed character gender values', () => {
    const parsed = characterMapItemSchema.parse({
      name: 'Kai',
      verbalized_form: 'Kai',
      gender: 'female',
      aliases: [],
      notes: null,
      source: 'manual',
      confidence: 1.0,
      source_trace: [],
    });

    expect(parsed.gender).toBe('female');
    expect(parsed.aliases).toEqual([]);
  });

  it('accepts character map payload with allowed genders in rows', () => {
    const parsed = characterMapSchema.parse({
      project_id: 101,
      character_map_finalized: false,
      characters: [
        {
          name: 'Kai',
          verbalized_form: 'Kai',
          gender: 'male',
          aliases: [],
          notes: null,
          source: 'manual',
          confidence: 1.0,
          source_trace: [],
        },
        {
          name: 'Lio',
          verbalized_form: 'Lio',
          gender: 'neutral',
          aliases: ['Li'],
          notes: 'Minor',
          source: 'manual',
          confidence: 0.8,
          source_trace: [],
        },
      ],
    });

    expect(parsed.characters).toHaveLength(2);
    expect(parsed.characters[1].gender).toBe('neutral');
  });

  it('rejects character payload with unsupported gender values', () => {
    expect(() =>
      characterMapItemSchema.parse({
        name: 'Kai',
        verbalized_form: 'Kai',
        gender: 'binary',
        aliases: [],
        notes: null,
        source: 'manual',
        confidence: 1.0,
        source_trace: [],
      }),
    ).toThrow();
  });
});
