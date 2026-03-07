import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import type { ProjectControlPanelProjectListRequestDto } from '@/app/schemas/api';

export type DashboardListQueryState = {
  page: number;
  page_size: number;
  status?: ProjectControlPanelProjectListRequestDto['status'];
  selected_mode?: ProjectControlPanelProjectListRequestDto['selected_mode'];
  last_run_status?: ProjectControlPanelProjectListRequestDto['last_run_status'];
  next_required_action?: ProjectControlPanelProjectListRequestDto['next_required_action'];
};

type UIRouteState = {
  dashboardListQuery: DashboardListQueryState;
  lastProjectRouteById: Record<number, string>;
  setDashboardListQuery: (query: DashboardListQueryState) => void;
  setProjectLastRoute: (projectId: number, route: string) => void;
  getProjectLastRoute: (projectId: number) => string | null;
  resetUiRouteState: () => void;
};

const initialUiRouteState = {
  dashboardListQuery: {
    page: 1,
    page_size: 20,
  },
  lastProjectRouteById: {},
} satisfies Pick<UIRouteState, 'dashboardListQuery' | 'lastProjectRouteById'>;

function areDashboardQueriesEqual(left: DashboardListQueryState, right: DashboardListQueryState) {
  return (
    left.page === right.page &&
    left.page_size === right.page_size &&
    left.status === right.status &&
    left.selected_mode === right.selected_mode &&
    left.last_run_status === right.last_run_status &&
    left.next_required_action === right.next_required_action
  );
}

export const useUiRouteStateStore = create<UIRouteState>()(
  persist(
    (set, get) => ({
      ...initialUiRouteState,
      setDashboardListQuery: (query) =>
        set((state) => {
          if (areDashboardQueriesEqual(state.dashboardListQuery, query)) {
            return state;
          }
          return { dashboardListQuery: query };
        }),
      setProjectLastRoute: (projectId, route) =>
        set((state) => {
          const projectRoutePrefix = `/projects/${projectId}/`;
          if (!route.startsWith(projectRoutePrefix)) {
            return state;
          }
          const current = state.lastProjectRouteById[projectId];
          if (current === route) {
            return state;
          }
          return {
            lastProjectRouteById: {
              ...state.lastProjectRouteById,
              [projectId]: route,
            },
          };
        }),
      getProjectLastRoute: (projectId) => get().lastProjectRouteById[projectId] ?? null,
      resetUiRouteState: () => set(initialUiRouteState),
    }),
    {
      name: 'nipe-ui-route-state',
      partialize: (state) => ({
        dashboardListQuery: state.dashboardListQuery,
        lastProjectRouteById: state.lastProjectRouteById,
      }),
    },
  ),
);
