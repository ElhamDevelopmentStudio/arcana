import { lazy, Suspense, type ReactNode } from 'react';
import type { RouteObject } from 'react-router-dom';

import { MainShell } from '@/app/main-shell';
const DashboardPage = lazy(() =>
  import('@/pages/dashboard/dashboard-page').then((module) => ({ default: module.DashboardPage })),
);

const ProjectCharactersPage = lazy(() =>
  import('@/pages/projects/project-characters-page').then((module) => ({ default: module.ProjectCharactersPage })),
);
const ProjectDashboardsPage = lazy(() =>
  import('@/pages/projects/project-dashboards-page').then((module) => ({ default: module.ProjectDashboardsPage })),
);
const ProjectExportPage = lazy(() =>
  import('@/pages/projects/project-export-page').then((module) => ({ default: module.ProjectExportPage })),
);
const ProjectModePage = lazy(() =>
  import('@/pages/projects/project-mode-page').then((module) => ({ default: module.ProjectModePage })),
);
const ProjectNewPage = lazy(() =>
  import('@/pages/projects/project-new-page').then((module) => ({ default: module.ProjectNewPage })),
);
const ProjectPipelineSetupPage = lazy(() =>
  import('@/pages/projects/project-pipeline-setup-page').then((module) => ({ default: module.ProjectPipelineSetupPage })),
);
const ProjectRunMonitorPage = lazy(() =>
  import('@/pages/projects/project-run-monitor-page').then((module) => ({ default: module.ProjectRunMonitorPage })),
);
const ProjectSpeakerReviewPage = lazy(() =>
  import('@/pages/projects/project-speaker-review-page').then((module) => ({ default: module.ProjectSpeakerReviewPage })),
);
const ProjectEmotionReviewPage = lazy(() =>
  import('@/pages/projects/project-emotion-review-page').then((module) => ({ default: module.ProjectEmotionReviewPage })),
);
const ProjectLowConfidenceReviewPage = lazy(() =>
  import('@/pages/projects/project-low-confidence-review-page').then((module) => ({
    default: module.ProjectLowConfidenceReviewPage,
  })),
);
const ProjectLowConfidenceReviewGuidePage = lazy(() =>
  import('@/pages/projects/project-low-confidence-review-guide-page').then((module) => ({
    default: module.ProjectLowConfidenceReviewGuidePage,
  })),
);

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
