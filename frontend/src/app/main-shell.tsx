import { Profiler, useCallback, useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useParams } from 'react-router-dom';
import { LayoutDashboard, Plus, Settings, ChevronLeft, ChevronRight, BookOpenText } from 'lucide-react';

import { cn } from '@/lib/utils';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { useCriticalRoutePrefetch } from '@/features/workflow/prefetch/critical-route-prefetch';
import {
  completeRouteNavigationMeasurement,
  reportRenderCostMetric,
  startRouteNavigationMeasurement,
} from '@/features/workflow/performance/performance-instrumentation';
import { useUiRouteStateStore } from '@/app/state/ui-route-state-store';

type GlobalNavItem = {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
  end?: boolean;
};

const GLOBAL_NAV: GlobalNavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/projects/new', label: 'New Project', icon: Plus },
];

function getProjectIdFromPath(pathname: string, fallback: string | undefined): string | null {
  if (fallback) return fallback;
  const match = pathname.match(/\/projects\/([^/]+)/);
  if (!match || match[1] === 'new') return null;
  return match[1];
}

export function MainShell() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const routePathWithSearch = `${location.pathname}${location.search}`;
  const params = useParams<{ project_id?: string }>();
  const projectId = getProjectIdFromPath(location.pathname, params.project_id);
  const currentProjectId = parseProjectIdParam(projectId ?? undefined);
  const setProjectLastRoute = useUiRouteStateStore((state) => state.setProjectLastRoute);
  const pendingNavigationPathRef = useRef<string | null>(null);

  useCriticalRoutePrefetch({ pathname: location.pathname, projectId: currentProjectId });

  useEffect(() => {
    const handleLinkNavigationStart = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (!(event.target instanceof Element)) return;
      const anchor = event.target.closest('a[href]');
      if (!(anchor instanceof HTMLAnchorElement)) return;
      if (anchor.target && anchor.target !== '_self') return;
      const href = anchor.getAttribute('href');
      if (!href || href.startsWith('#')) return;
      let nextUrl: URL;
      try { nextUrl = new URL(anchor.href, window.location.origin); } catch { return; }
      if (nextUrl.origin !== window.location.origin) return;
      const nextPathWithSearch = `${nextUrl.pathname}${nextUrl.search}`;
      const currentPathWithSearch = `${window.location.pathname}${window.location.search}`;
      if (nextPathWithSearch === currentPathWithSearch) return;
      pendingNavigationPathRef.current = nextPathWithSearch;
      startRouteNavigationMeasurement(nextPathWithSearch);
    };
    document.addEventListener('click', handleLinkNavigationStart, true);
    return () => document.removeEventListener('click', handleLinkNavigationStart, true);
  }, []);

  useEffect(() => {
    if (pendingNavigationPathRef.current !== routePathWithSearch) return;
    completeRouteNavigationMeasurement(routePathWithSearch);
    pendingNavigationPathRef.current = null;
  }, [routePathWithSearch]);

  const handleRouteRender = useCallback(
    (_id: string, phase: 'mount' | 'update' | 'nested-update', actualDuration: number) => {
      reportRenderCostMetric({ component: 'main-shell-route-content', phase, actualDurationMs: actualDuration, routePath: routePathWithSearch });
    },
    [routePathWithSearch],
  );

  useEffect(() => {
    if (currentProjectId === null) return;
    const routePrefix = `/projects/${currentProjectId}/`;
    if (!location.pathname.startsWith(routePrefix)) return;
    setProjectLastRoute(currentProjectId, `${location.pathname}${location.search}`);
  }, [currentProjectId, location.pathname, location.search, setProjectLastRoute]);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground">
      <a
        className="sr-only z-50 rounded-md bg-background px-3 py-2 text-sm font-medium text-foreground focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        data-testid="skip-to-main-link"
        href="#app-main-content"
      >
        Skip to main content
      </a>

      {/* Sidebar */}
      <aside
        aria-label="Global navigation"
        className={cn(
          'flex flex-col border-r border-white/10 bg-sidebar transition-all duration-200',
          collapsed ? 'w-16' : 'w-60',
        )}
      >
        {/* Logo */}
        <div className={cn('flex h-14 shrink-0 items-center border-b border-white/10', collapsed ? 'justify-center px-0' : 'gap-2.5 px-4')}>
          <Link
            aria-label="Nipe home"
            className="flex items-center gap-2.5"
            to="/dashboard"
          >
            <span className="grid size-7 shrink-0 place-items-center rounded bg-foreground text-background">
              <BookOpenText size={14} />
            </span>
            {!collapsed && (
              <span className="text-sm font-semibold tracking-tight text-foreground">nipe</span>
            )}
          </Link>
        </div>

        {/* Nav items */}
        <nav aria-label="Main navigation" className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {GLOBAL_NAV.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-md px-2.5 py-2 text-sm transition-colors duration-100',
                    isActive
                      ? 'bg-sidebar-accent text-foreground'
                      : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
                    collapsed && 'justify-center px-0',
                  )
                }
                end={item.end}
                title={collapsed ? item.label : undefined}
                to={item.to}
              >
                <Icon className="shrink-0" size={16} />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            );
          })}
        </nav>

        {/* Bottom: settings + collapse */}
        <div className={cn('shrink-0 border-t border-white/10 p-2 space-y-0.5')}>
          <NavLink
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-md px-2.5 py-2 text-sm transition-colors duration-100',
                isActive
                  ? 'bg-sidebar-accent text-foreground'
                  : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
                collapsed && 'justify-center px-0',
              )
            }
            title={collapsed ? 'Settings' : undefined}
            to="/settings"
          >
            <Settings className="shrink-0" size={16} />
            {!collapsed && <span>Settings</span>}
          </NavLink>

          <button
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-sm text-muted-foreground transition-colors duration-100 hover:bg-sidebar-accent/60 hover:text-foreground"
            onClick={() => setCollapsed((c) => !c)}
            type="button"
          >
            {collapsed ? (
              <ChevronRight className="mx-auto shrink-0" size={16} />
            ) : (
              <>
                <ChevronLeft className="shrink-0" size={16} />
                <span>Collapse</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main
        aria-labelledby="app-route-title"
        className="flex min-w-0 flex-1 flex-col overflow-hidden"
        id="app-main-content"
        tabIndex={-1}
      >
        <Profiler id="main-shell-route-content" onRender={handleRouteRender}>
          <Outlet />
        </Profiler>
      </main>
    </div>
  );
}
