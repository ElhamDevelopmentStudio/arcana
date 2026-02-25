export function parseProjectIdParam(projectParam: string | undefined): number | null {
  if (!projectParam) {
    return null;
  }
  const parsed = Number(projectParam);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

export function projectRoute(
  projectId: number,
  path:
    | 'mode'
    | 'characters'
    | 'pipeline-setup'
    | 'run-monitor'
    | 'review/speakers'
    | 'export'
    | 'dashboards',
) {
  return `/projects/${projectId}/${path}`;
}
