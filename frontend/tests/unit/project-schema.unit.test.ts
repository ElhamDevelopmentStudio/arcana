import { describe, expect, it } from 'vitest';

import { projectSchema } from '@/app/schemas/api';

describe('projectSchema', () => {
  it('parses project payload with nullable ingestion_timestamp', () => {
    const parsed = projectSchema.parse({
      id: 101,
      title: 'Shadow Slave PoC',
      selected_mode: 'audiobook',
      selected_modes: ['audiobook'],
      configuration_snapshot_id: 'project-101-config-initial',
      ingestion_timestamp: null,
      created_at: '2026-02-25T00:00:00Z',
    });

    expect(parsed.id).toBe(101);
    expect(parsed.ingestion_timestamp).toBeNull();
    expect(parsed.selected_modes).toEqual(['audiobook']);
    expect(parsed.configuration_snapshot_id).toBe('project-101-config-initial');
  });
});
