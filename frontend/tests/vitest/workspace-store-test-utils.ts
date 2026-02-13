import { useUiRouteStateStore } from '@/app/state/ui-route-state-store';
import { useWorkspaceStore } from '@/app/state/workspace-store';

const initialWorkspaceState = {
  projectId: null,
  projectTitle: null,
  selectedMode: null,
  chapterCount: null,
  runId: null,
};

export function resetWorkspaceStore() {
  useWorkspaceStore.setState(initialWorkspaceState);
  useWorkspaceStore.persist.clearStorage();
  window.localStorage.removeItem('nipe-workspace');

  useUiRouteStateStore.getState().resetUiRouteState();
  useUiRouteStateStore.persist.clearStorage();
  window.localStorage.removeItem('nipe-ui-route-state');
}
