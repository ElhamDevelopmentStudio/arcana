import { describe, expect, it } from 'vitest';

import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';

describe('project-route utils', () => {
  it('parses valid positive integer project id values', () => {
    expect(parseProjectIdParam('1')).toBe(1);
    expect(parseProjectIdParam('42')).toBe(42);
  });

  it('returns null for invalid project id values', () => {
    expect(parseProjectIdParam(undefined)).toBeNull();
    expect(parseProjectIdParam('')).toBeNull();
    expect(parseProjectIdParam('0')).toBeNull();
    expect(parseProjectIdParam('-5')).toBeNull();
    expect(parseProjectIdParam('abc')).toBeNull();
  });

  it('builds route paths for project workflow pages', () => {
    expect(projectRoute(7, 'mode')).toBe('/projects/7/mode');
    expect(projectRoute(7, 'pipeline-setup')).toBe('/projects/7/pipeline-setup');
    expect(projectRoute(7, 'dashboards')).toBe('/projects/7/dashboards');
    expect(projectRoute(7, 'review/emotions')).toBe('/projects/7/review/emotions');
    expect(projectRoute(7, 'review/low-confidence')).toBe('/projects/7/review/low-confidence');
    expect(projectRoute(7, 'guide/low-confidence-review')).toBe('/projects/7/guide/low-confidence-review');
    expect(projectRoute(7, 'review/speakers')).toBe('/projects/7/review/speakers');
  });
});
