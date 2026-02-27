import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  useProjectLLMSettingsQuery,
  useUpdateProjectLLMSettingsMutation,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

export function ProjectSettingsPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;
  const projectLLMSettingsQuery = useProjectLLMSettingsQuery(projectId);
  const updateProjectLLMSettingsMutation = useUpdateProjectLLMSettingsMutation(projectId);
  const [llmEnabledDraft, setLlmEnabledDraft] = useState(false);

  useEffect(() => {
    if (projectLLMSettingsQuery.data === undefined) {
      return;
    }
    setLlmEnabledDraft(projectLLMSettingsQuery.data.llm_enabled);
  }, [projectLLMSettingsQuery.data]);

  const hasUnsavedChanges =
    projectLLMSettingsQuery.data !== undefined &&
    llmEnabledDraft !== projectLLMSettingsQuery.data.llm_enabled;

  async function handleSaveProjectLLMSettings() {
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }

    try {
      const response = await updateProjectLLMSettingsMutation.trigger({
        llm_enabled: llmEnabledDraft,
      });
      setLlmEnabledDraft(response.llm_enabled);
      toast.success(`Project LLM is now ${response.llm_enabled ? 'enabled' : 'disabled'}.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update project LLM settings.');
    }
  }

  return (
    <WorkflowPageShell
      description="Project-scoped settings and policy controls."
      step="Settings"
      title="Project Settings"
    >
      <Card data-testid="project-settings-llm-panel">
        <CardHeader>
          <CardTitle>LLM Settings</CardTitle>
          <CardDescription>
            Toggle project-level LLM execution policy using `GET/PUT /api/projects/:project_id/llm`.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>Project: {projectId ?? 'n/a'}</p>
          {projectId === null ? <Badge variant="outline">Project required</Badge> : null}
          {projectLLMSettingsQuery.isLoading ? (
            <p data-testid="project-settings-llm-loading">Loading LLM settings...</p>
          ) : null}
          {projectLLMSettingsQuery.error ? (
            <p className="text-destructive" data-testid="project-settings-llm-error">
              {projectLLMSettingsQuery.error.message}
            </p>
          ) : null}

          {projectLLMSettingsQuery.data ? (
            <div className="space-y-3 rounded-xl border border-panel-border/70 bg-muted/35 p-3">
              <p data-testid="project-settings-llm-current">
                Current backend value:{' '}
                <strong className="text-foreground">{projectLLMSettingsQuery.data.llm_enabled ? 'enabled' : 'disabled'}</strong>
              </p>

              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="project-settings-llm-toggle">LLM enabled</Label>
                <Switch
                  id="project-settings-llm-toggle"
                  data-testid="project-settings-llm-toggle"
                  checked={llmEnabledDraft}
                  disabled={updateProjectLLMSettingsMutation.isMutating}
                  onCheckedChange={setLlmEnabledDraft}
                />
              </div>

              <div className="flex items-center justify-between gap-3">
                <p data-testid="project-settings-llm-draft">
                  Draft value: <strong className="text-foreground">{llmEnabledDraft ? 'enabled' : 'disabled'}</strong>
                </p>
                <Button
                  data-testid="project-settings-llm-save"
                  disabled={!hasUnsavedChanges || updateProjectLLMSettingsMutation.isMutating}
                  onClick={() => void handleSaveProjectLLMSettings()}
                  type="button"
                >
                  {updateProjectLLMSettingsMutation.isMutating ? 'Saving...' : 'Save LLM setting'}
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </WorkflowPageShell>
  );
}
