import { useEffect } from 'react';

import { projectRoute } from '@/features/workflow/utils/project-route';
import { prefetchRouteModule } from '@/router/main';

type CriticalRoutePrefetchContext = {
  pathname: string;
  projectId: number | null;
};

function isRoute(pathname: string, pattern: RegExp) {
  return pattern.test(pathname);
}

export function getCriticalRoutePrefetchTargets({
  pathname,
  projectId,
}: CriticalRoutePrefetchContext): string[] {
  if (pathname === '/') {
    return ['/dashboard', '/projects/new'];
  }

  if (pathname === '/dashboard') {
    return ['/projects/new'];
  }

  if (pathname === '/projects/new' && projectId !== null) {
    return [projectRoute(projectId, 'mode')];
  }

  if (isRoute(pathname, /^\/projects\/[^/]+\/mode$/) && projectId !== null) {
    return [projectRoute(projectId, 'characters')];
  }

  if (isRoute(pathname, /^\/projects\/[^/]+\/characters$/) && projectId !== null) {
    return [projectRoute(projectId, 'pipeline-setup')];
  }

  if (isRoute(pathname, /^\/projects\/[^/]+\/pipeline-setup$/) && projectId !== null) {
    return [projectRoute(projectId, 'run-monitor')];
  }

  if (isRoute(pathname, /^\/projects\/[^/]+\/run-monitor$/) && projectId !== null) {
    return [projectRoute(projectId, 'export'), projectRoute(projectId, 'dashboards')];
  }

  if (isRoute(pathname, /^\/projects\/[^/]+\/export$/) && projectId !== null) {
    return [projectRoute(projectId, 'dashboards')];
  }

  return [];
}

export function useCriticalRoutePrefetch(context: CriticalRoutePrefetchContext) {
  useEffect(() => {
    if (import.meta.env.MODE === 'test') {
      return;
    }
    const targets = getCriticalRoutePrefetchTargets(context);
    for (const target of targets) {
      prefetchRouteModule(target);
    }
  }, [context.pathname, context.projectId]);
}
