import { lazy, Suspense, type ReactNode } from 'react';
import type { RouteObject } from 'react-router-dom';

import { MainShell } from '@/app/main-shell';

const loadDashboardPage = () => import('@/pages/dashboard/dashboard-page');
const loadProjectCharactersPage = () => import('@/pages/projects/project-characters-page');
const loadProjectDashboardsPage = () => import('@/pages/projects/project-dashboards-page');
const loadProjectExportPage = () => import('@/pages/projects/project-export-page');
const loadProjectModePage = () => import('@/pages/projects/project-mode-page');
const loadProjectNewPage = () => import('@/pages/projects/project-new-page');
const loadProjectPipelineSetupPage = () => import('@/pages/projects/project-pipeline-setup-page');
const loadProjectRunMonitorPage = () => import('@/pages/projects/project-run-monitor-page');
const loadProjectSpeakerReviewPage = () => import('@/pages/projects/project-speaker-review-page');
const loadProjectEmotionReviewPage = () => import('@/pages/projects/project-emotion-review-page');
const loadProjectLowConfidenceReviewPage = () => import('@/pages/projects/project-low-confidence-review-page');
const loadProjectLowConfidenceReviewGuidePage = () => import('@/pages/projects/project-low-confidence-review-guide-page');

const DashboardPage = lazy(() => loadDashboardPage().then((module) => ({ default: module.DashboardPage })));
const ProjectCharactersPage = lazy(() =>
  loadProjectCharactersPage().then((module) => ({ default: module.ProjectCharactersPage })),
);
const ProjectDashboardsPage = lazy(() =>
  loadProjectDashboardsPage().then((module) => ({ default: module.ProjectDashboardsPage })),
);
const ProjectExportPage = lazy(() => loadProjectExportPage().then((module) => ({ default: module.ProjectExportPage })));
const ProjectModePage = lazy(() => loadProjectModePage().then((module) => ({ default: module.ProjectModePage })));
const ProjectNewPage = lazy(() => loadProjectNewPage().then((module) => ({ default: module.ProjectNewPage })));
const ProjectPipelineSetupPage = lazy(() =>
  loadProjectPipelineSetupPage().then((module) => ({ default: module.ProjectPipelineSetupPage })),
);
const ProjectRunMonitorPage = lazy(() =>
  loadProjectRunMonitorPage().then((module) => ({ default: module.ProjectRunMonitorPage })),
);
const ProjectSpeakerReviewPage = lazy(() =>
  loadProjectSpeakerReviewPage().then((module) => ({ default: module.ProjectSpeakerReviewPage })),
);
const ProjectEmotionReviewPage = lazy(() =>
  loadProjectEmotionReviewPage().then((module) => ({ default: module.ProjectEmotionReviewPage })),
);
const ProjectLowConfidenceReviewPage = lazy(() =>
  loadProjectLowConfidenceReviewPage().then((module) => ({
    default: module.ProjectLowConfidenceReviewPage,
  })),
);
const ProjectLowConfidenceReviewGuidePage = lazy(() =>
  loadProjectLowConfidenceReviewGuidePage().then((module) => ({
    default: module.ProjectLowConfidenceReviewGuidePage,
  })),
);

const ROUTE_MODULE_PREFETCHERS: Array<{ pattern: RegExp; load: () => Promise<unknown> }> = [
  { pattern: /^\/dashboard$/, load: loadDashboardPage },
  { pattern: /^\/projects\/new$/, load: loadProjectNewPage },
  { pattern: /^\/projects\/[^/]+\/mode$/, load: loadProjectModePage },
  { pattern: /^\/projects\/[^/]+\/characters$/, load: loadProjectCharactersPage },
  { pattern: /^\/projects\/[^/]+\/pipeline-setup$/, load: loadProjectPipelineSetupPage },
  { pattern: /^\/projects\/[^/]+\/run-monitor$/, load: loadProjectRunMonitorPage },
  { pattern: /^\/projects\/[^/]+\/review\/speakers$/, load: loadProjectSpeakerReviewPage },
  { pattern: /^\/projects\/[^/]+\/review\/emotions$/, load: loadProjectEmotionReviewPage },
  { pattern: /^\/projects\/[^/]+\/review\/low-confidence$/, load: loadProjectLowConfidenceReviewPage },
  { pattern: /^\/projects\/[^/]+\/guide\/low-confidence-review$/, load: loadProjectLowConfidenceReviewGuidePage },
  { pattern: /^\/projects\/[^/]+\/export$/, load: loadProjectExportPage },
  { pattern: /^\/projects\/[^/]+\/dashboards$/, load: loadProjectDashboardsPage },
];

export function prefetchRouteModule(pathname: string) {
  const matched = ROUTE_MODULE_PREFETCHERS.find((entry) => entry.pattern.test(pathname));
  if (!matched) {
    return;
  }
  void matched.load();
}

const ROUTE_SUSPENSE_FALLBACK = (
  <div className="flex h-full items-center justify-center p-8 text-sm text-muted-foreground">Loading step...</div>
);

function SuspendedRoute({ children }: { children: ReactNode }) {
  return <Suspense fallback={ROUTE_SUSPENSE_FALLBACK}>{children}</Suspense>;
}

export const mainRouter: RouteObject[] = [
  {
    element: <MainShell />,
    children: [
      {
        path: 'dashboard',
        element: <SuspendedRoute><DashboardPage /></SuspendedRoute>,
      },
      {
        path: 'projects/new',
        element: <SuspendedRoute><ProjectNewPage /></SuspendedRoute>,
      },
      {
        path: 'projects/:project_id/mode',
        element: <SuspendedRoute><ProjectModePage /></SuspendedRoute>,
      },
      {
        path: 'projects/:project_id/characters',
        element: <SuspendedRoute><ProjectCharactersPage /></SuspendedRoute>,
      },
      {
        path: 'projects/:project_id/pipeline-setup',
        element: <SuspendedRoute><ProjectPipelineSetupPage /></SuspendedRoute>,
      },
      {
        path: 'projects/:project_id/run-monitor',
        element: <SuspendedRoute><ProjectRunMonitorPage /></SuspendedRoute>,
      },
      {
        path: 'projects/:project_id/review/speakers',
        element: <SuspendedRoute><ProjectSpeakerReviewPage /></SuspendedRoute>,
      },
      {
        path: 'projects/:project_id/review/emotions',
        element: <SuspendedRoute><ProjectEmotionReviewPage /></SuspendedRoute>,
      },
      {
        path: 'projects/:project_id/review/low-confidence',
        element: <SuspendedRoute><ProjectLowConfidenceReviewPage /></SuspendedRoute>,
      },
      {
        path: 'projects/:project_id/guide/low-confidence-review',
        element: <SuspendedRoute><ProjectLowConfidenceReviewGuidePage /></SuspendedRoute>,
      },
      {
        path: 'projects/:project_id/export',
        element: <SuspendedRoute><ProjectExportPage /></SuspendedRoute>,
      },
      {
        path: 'projects/:project_id/dashboards',
        element: <SuspendedRoute><ProjectDashboardsPage /></SuspendedRoute>,
      },
    ],
  },
];
