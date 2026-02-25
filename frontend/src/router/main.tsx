import type { RouteObject } from 'react-router-dom';
import { Navigate } from 'react-router-dom';

import { MainShell } from '@/app/main-shell';
import { ProjectCharactersPage } from '@/pages/projects/project-characters-page';
import { ProjectDashboardsPage } from '@/pages/projects/project-dashboards-page';
import { ProjectExportPage } from '@/pages/projects/project-export-page';
import { ProjectModePage } from '@/pages/projects/project-mode-page';
import { ProjectNewPage } from '@/pages/projects/project-new-page';
import { ProjectPipelineSetupPage } from '@/pages/projects/project-pipeline-setup-page';
import { ProjectRunMonitorPage } from '@/pages/projects/project-run-monitor-page';

export const mainRouter: RouteObject[] = [
  {
    element: <MainShell />,
    children: [
      {
        index: true,
        element: <Navigate to="/projects/new" replace />,
      },
      {
        path: 'projects/new',
        element: <ProjectNewPage />,
      },
      {
        path: 'projects/:project_id/mode',
        element: <ProjectModePage />,
      },
      {
        path: 'projects/:project_id/characters',
        element: <ProjectCharactersPage />,
      },
      {
        path: 'projects/:project_id/pipeline-setup',
        element: <ProjectPipelineSetupPage />,
      },
      {
        path: 'projects/:project_id/run-monitor',
        element: <ProjectRunMonitorPage />,
      },
      {
        path: 'projects/:project_id/export',
        element: <ProjectExportPage />,
      },
      {
        path: 'projects/:project_id/dashboards',
        element: <ProjectDashboardsPage />,
      },
    ],
  },
];
