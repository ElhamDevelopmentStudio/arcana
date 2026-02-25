import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type WorkspaceState = {
  projectId: number | null;
  projectTitle: string | null;
  selectedMode: string | null;
  chapterCount: number | null;
  runId: number | null;
  setProject: (payload: { projectId: number; projectTitle: string; selectedMode: string | null }) => void;
  setChapterCount: (chapterCount: number) => void;
  setSelectedMode: (selectedMode: string) => void;
  setRunId: (runId: number | null) => void;
  resetWorkspace: () => void;
};

const initialWorkspaceState = {
  projectId: null,
  projectTitle: null,
  selectedMode: null,
  chapterCount: null,
  runId: null,
} as const;

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set) => ({
      ...initialWorkspaceState,
      setProject: ({ projectId, projectTitle, selectedMode }) =>
        set({
          projectId,
          projectTitle,
          selectedMode,
          chapterCount: null,
          runId: null,
        }),
      setChapterCount: (chapterCount) => set({ chapterCount }),
      setSelectedMode: (selectedMode) => set({ selectedMode }),
      setRunId: (runId) => set({ runId }),
      resetWorkspace: () => set(initialWorkspaceState),
    }),
    {
      name: 'nipe-workspace',
      partialize: (state) => ({
        projectId: state.projectId,
        projectTitle: state.projectTitle,
        selectedMode: state.selectedMode,
        chapterCount: state.chapterCount,
        runId: state.runId,
      }),
    },
  ),
);
