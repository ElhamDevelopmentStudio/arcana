import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

export function ProjectWorkspaceHomePage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const projectId = parseProjectIdParam(params.project_id);

  useEffect(() => {
    if (projectId !== null) {
      navigate(`/projects/${projectId}/overview`, { replace: true });
    } else {
      navigate('/dashboard', { replace: true });
    }
  }, [projectId, navigate]);

  return null;
}
