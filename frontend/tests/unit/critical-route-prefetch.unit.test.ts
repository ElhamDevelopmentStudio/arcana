import { describe, expect, it } from 'vitest';

import { getCriticalRoutePrefetchTargets } from '@/features/workflow/prefetch/critical-route-prefetch';

describe('getCriticalRoutePrefetchTargets', () => {
  it('prefetches dashboard and project creation routes from landing', () => {
    const targets = getCriticalRoutePrefetchTargets({
      pathname: '/',
      projectId: null,
    });

    expect(targets).toEqual(['/dashboard', '/projects/new']);
  });

  it('prefetches mode step after project creation route when project id exists', () => {
    const targets = getCriticalRoutePrefetchTargets({
      pathname: '/projects/new',
      projectId: 44,
    });

    expect(targets).toEqual(['/projects/44/mode']);
  });

  it('prefetches characters after mode selection', () => {
    const targets = getCriticalRoutePrefetchTargets({
      pathname: '/projects/44/mode',
      projectId: 44,
    });

    expect(targets).toEqual(['/projects/44/characters']);
  });

  it('prefetches export and dashboards after run monitor', () => {
    const targets = getCriticalRoutePrefetchTargets({
      pathname: '/projects/44/run-monitor',
      projectId: 44,
    });

    expect(targets).toEqual(['/projects/44/export', '/projects/44/dashboards']);
  });

  it('returns no targets for unrelated routes', () => {
    const targets = getCriticalRoutePrefetchTargets({
      pathname: '/auth',
      projectId: null,
    });

    expect(targets).toEqual([]);
  });
});
