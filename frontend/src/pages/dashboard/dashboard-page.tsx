import { useMemo, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, BookOpen } from 'lucide-react';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { useUiRouteStateStore } from '@/app/state/ui-route-state-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ProjectCard } from '@/components/projects/project-card';
import {
  useProjectControlPanelProjectListQuery,
  useProjectControlPanelSummaryQuery,
} from '@/features/workflow/api/workflow-hooks';
import { cn } from '@/lib/utils';
import type { ProjectControlPanelProjectListItemDto } from '@/app/schemas/api';

const FILTER_TABS = [
  { id: 'all', label: 'All' },
  { id: 'active', label: 'Active' },
  { id: 'archived', label: 'Archived' },
] as const;

type FilterTab = (typeof FILTER_TABS)[number]['id'];

function toWorkflowRoute(projectId: number, nextRequiredAction: string) {
  if (nextRequiredAction === 'select_mode') return `/projects/${projectId}/mode`;
  if (nextRequiredAction === 'run' || nextRequiredAction === 'configure') return `/projects/${projectId}/pipeline-setup`;
  if (nextRequiredAction === 'export') return `/projects/${projectId}/export`;
  if (nextRequiredAction === 'rerun') return `/projects/${projectId}/run-monitor`;
  return `/projects/${projectId}/overview`;
}

function DashboardEmpty() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="mb-4 grid size-12 place-items-center rounded-xl border border-white/10 bg-card text-muted-foreground">
        <BookOpen size={22} />
      </div>
      <h3 className="text-base font-semibold text-foreground">No projects yet</h3>
      <p className="mt-1 text-sm text-muted-foreground">Create your first project to get started.</p>
      <Button
        className="mt-6"
        onClick={() => navigate('/projects/new')}
        type="button"
      >
        <Plus size={14} />
        Create a project
      </Button>
    </div>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const setProject = useWorkspaceStore((state) => state.setProject);
  const getProjectLastRoute = useUiRouteStateStore((state) => state.getProjectLastRoute);
  const [activeTab, setActiveTab] = useState<FilterTab>('all');
  const [search, setSearch] = useState('');

  const listQuery = useProjectControlPanelProjectListQuery(true, { page: 1, page_size: 100 });
  const summaryQuery = useProjectControlPanelSummaryQuery(true);
  const activeRunCount = summaryQuery.data?.active_run_count ?? 0;
  const items: ProjectControlPanelProjectListItemDto[] = listQuery.data?.items ?? [];

  const hasActiveRows = items.some(
    (item) => item.status === 'running' || item.last_run_status === 'running' || item.last_run_status === 'queued',
  );
  const shouldAutoRefresh = activeRunCount > 0 || hasActiveRows;

  useEffect(() => {
    if (!shouldAutoRefresh) return;
    const id = window.setInterval(() => {
      void listQuery.mutate();
      void summaryQuery.mutate();
    }, 5000);
    return () => window.clearInterval(id);
  }, [shouldAutoRefresh, listQuery, summaryQuery]);

  const filteredItems = useMemo(() => {
    let result = items;
    if (activeTab === 'active') {
      result = result.filter((i) => i.status !== 'archived');
    } else if (activeTab === 'archived') {
      result = result.filter((i) => i.status === 'archived');
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (i) =>
          String(i.project_id).includes(q) ||
          (i.selected_mode && i.selected_mode.toLowerCase().includes(q)),
      );
    }
    return result;
  }, [items, activeTab, search]);

  const isLoading = listQuery.isLoading && listQuery.data === undefined;

  function handleOpenProject(item: ProjectControlPanelProjectListItemDto) {
    setProject({
      projectId: item.project_id,
      projectTitle: `Project ${item.project_id}`,
      selectedMode: item.selected_mode,
    });
    const remembered = getProjectLastRoute(item.project_id);
    navigate(remembered ?? toWorkflowRoute(item.project_id, item.next_required_action));
  }

  return (
    <div className="flex h-full flex-col overflow-auto">
      <div className="flex-1 px-6 py-8 lg:px-10">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground" id="app-route-title">
            My Projects
          </h1>
          <Button
            data-testid="dashboard-create-project"
            onClick={() => navigate('/projects/new')}
            type="button"
          >
            <Plus size={14} />
            New Project
          </Button>
        </div>

        {/* Filter bar */}
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <div className="flex gap-1 rounded-lg border border-white/10 bg-card p-1">
            {FILTER_TABS.map((tab) => (
              <button
                className={cn(
                  'rounded-md px-3 py-1 text-sm transition-colors',
                  activeTab === tab.id
                    ? 'bg-white/10 text-foreground'
                    : 'text-muted-foreground hover:text-foreground',
                )}
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                type="button"
              >
                {tab.label}
              </button>
            ))}
          </div>

          <Input
            className="ml-auto w-full max-w-xs"
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search projects…"
            type="search"
            value={search}
          />
        </div>

        {/* Project grid */}
        <div className="mt-8">
          {isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="dashboard-list-loading">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  className="h-36 animate-pulse rounded-xl border border-white/10 bg-card"
                  key={i}
                />
              ))}
            </div>
          ) : listQuery.error ? (
            <div className="rounded-xl border border-white/10 bg-card p-6 text-center" data-testid="dashboard-list-error">
              <p className="text-sm text-muted-foreground">Unable to load projects.</p>
              <Button
                className="mt-3"
                onClick={() => void listQuery.mutate()}
                size="sm"
                variant="outline"
              >
                Retry
              </Button>
            </div>
          ) : filteredItems.length === 0 ? (
            <DashboardEmpty />
          ) : (
            <div
              className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
              data-testid="dashboard-project-list"
            >
              {filteredItems.map((item) => (
                <ProjectCard
                  item={item}
                  key={item.project_id}
                  onClick={() => handleOpenProject(item)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
