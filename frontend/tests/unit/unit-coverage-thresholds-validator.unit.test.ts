import { describe, expect, it } from 'vitest';

import { evaluateCoverageThresholds } from '../../scripts/validate-unit-coverage-thresholds.mjs';

describe('unit coverage thresholds validator', () => {
  it('aggregates line coverage by module and passes when threshold is met', () => {
    const coverageSummary = {
      total: {
        lines: { total: 300, covered: 250, pct: 83.33 },
      },
      '/workspace/arcana/frontend/src/app/schemas/api.ts': {
        lines: { total: 100, covered: 90, pct: 90 },
      },
      '/workspace/arcana/frontend/src/app/schemas/run.ts': {
        lines: { total: 50, covered: 40, pct: 80 },
      },
      '/workspace/arcana/frontend/src/features/workflow/utils/project-route.ts': {
        lines: { total: 20, covered: 20, pct: 100 },
      },
    };
    const thresholds = {
      'src/app/schemas/': 80,
      'src/features/workflow/utils/': 90,
    };

    const results = evaluateCoverageThresholds(coverageSummary, thresholds, '/workspace/arcana/frontend');
    const byModule = new Map(results.map((result) => [result.module, result]));

    expect(byModule.get('src/app/schemas/')?.passed).toBe(true);
    expect(byModule.get('src/app/schemas/')?.coveragePercent).toBe(86.67);
    expect(byModule.get('src/features/workflow/utils/')?.passed).toBe(true);
    expect(byModule.get('src/features/workflow/utils/')?.coveragePercent).toBe(100);
  });

  it('fails when threshold is not met or module has no matching files', () => {
    const coverageSummary = {
      'src/app/schemas/api.ts': {
        lines: { total: 80, covered: 32, pct: 40 },
      },
    };
    const thresholds = {
      'src/app/schemas/': 50,
      'src/features/workflow/utils/': 60,
    };

    const results = evaluateCoverageThresholds(coverageSummary, thresholds, '/workspace/arcana/frontend');
    const byModule = new Map(results.map((result) => [result.module, result]));

    expect(byModule.get('src/app/schemas/')?.passed).toBe(false);
    expect(byModule.get('src/app/schemas/')?.reason).toBe('below_threshold');
    expect(byModule.get('src/features/workflow/utils/')?.passed).toBe(false);
    expect(byModule.get('src/features/workflow/utils/')?.reason).toBe('no_matching_files');
  });
});
