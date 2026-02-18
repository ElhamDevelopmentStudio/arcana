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
  useLLMProvidersQuery,
  useGrantProjectAccessMutation,
  useProjectAccessListQuery,
  useProjectLLMSettingsQuery,
  useUpdateLLMProviderStatusMutation,
  useUpdateProjectLLMSettingsMutation,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';

export function ProjectSettingsPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;
  const projectAccessListQuery = useProjectAccessListQuery(projectId);
  const projectLLMSettingsQuery = useProjectLLMSettingsQuery(projectId);
  const llmProvidersQuery = useLLMProvidersQuery(projectId !== null);
  const grantProjectAccessMutation = useGrantProjectAccessMutation(projectId);
  const updateProjectLLMSettingsMutation = useUpdateProjectLLMSettingsMutation(projectId);
  const updateLLMProviderStatusMutation = useUpdateLLMProviderStatusMutation(projectId);
  const [llmEnabledDraft, setLlmEnabledDraft] = useState(false);
  const [providerEnabledDraftByName, setProviderEnabledDraftByName] = useState<Record<string, boolean>>({});
  const [accessPrincipalIdDraft, setAccessPrincipalIdDraft] = useState('');
  const [accessPrincipalTypeDraft, setAccessPrincipalTypeDraft] = useState<'user' | 'service' | 'system'>('user');
  const [accessRoleDraft, setAccessRoleDraft] = useState<'owner' | 'editor' | 'viewer'>('viewer');

  useEffect(() => {
    if (projectLLMSettingsQuery.data === undefined) {
      return;
    }
    setLlmEnabledDraft(projectLLMSettingsQuery.data.llm_enabled);
  }, [projectLLMSettingsQuery.data]);

  useEffect(() => {
    if (!llmProvidersQuery.data?.providers) {
      return;
    }
    setProviderEnabledDraftByName(
      Object.fromEntries(llmProvidersQuery.data.providers.map((provider) => [provider.provider, provider.enabled])),
    );
  }, [llmProvidersQuery.data]);

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

  async function handleSaveProviderStatus(providerName: string) {
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    const draftEnabled = providerEnabledDraftByName[providerName];
    if (draftEnabled === undefined) {
      toast.error('Provider draft state is missing.');
      return;
    }

    try {
      const response = await updateLLMProviderStatusMutation.trigger({
        provider_name: providerName,
        enabled: draftEnabled,
      });
      setProviderEnabledDraftByName((previous) => ({
        ...previous,
        [response.provider]: response.enabled,
      }));
      toast.success(`Provider ${response.provider} is now ${response.enabled ? 'enabled' : 'disabled'}.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update provider status.');
    }
  }

  async function handleGrantProjectAccess() {
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    if (accessPrincipalIdDraft.trim().length === 0) {
      toast.error('Principal ID is required.');
      return;
    }
    try {
      const response = await grantProjectAccessMutation.trigger({
        principal_id: accessPrincipalIdDraft.trim(),
        principal_type: accessPrincipalTypeDraft,
        role: accessRoleDraft,
      });
      setAccessPrincipalIdDraft('');
      setAccessPrincipalTypeDraft('user');
      setAccessRoleDraft('viewer');
      toast.success(`Granted ${response.role} access to ${response.principal_id}.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to grant project access.');
    }
  }

  return (
    <WorkflowPageShell
      description="Project-scoped settings and policy controls."
      step="Settings"
      title="Project Settings"
    >
      <div className="grid gap-4 xl:grid-cols-3">
        <Card data-testid="project-settings-access-panel">
          <CardHeader>
            <CardTitle>Project Access</CardTitle>
            <CardDescription>
              Read current access grants via `GET /api/projects/:project_id/access`.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p
              className="rounded-md border border-dashed border-panel-border/70 bg-muted/30 px-3 py-2"
              data-testid="project-settings-access-no-auth-notice"
            >
              Authentication is not enabled in this environment. Access grants are configuration metadata only and do
              not enforce runtime authorization yet.
            </p>
            {projectAccessListQuery.isLoading ? (
              <p data-testid="project-settings-access-loading">Loading access grants...</p>
            ) : null}
            {projectAccessListQuery.error ? (
              <p className="text-destructive" data-testid="project-settings-access-error">
                {projectAccessListQuery.error.message}
              </p>
            ) : null}
            {projectAccessListQuery.data && projectAccessListQuery.data.grants.length === 0 ? (
              <p data-testid="project-settings-access-empty">No access grants configured.</p>
            ) : null}
            {(projectAccessListQuery.data?.grants ?? []).map((grant) => (
              <div
                key={grant.id}
                className="rounded-xl border border-panel-border/70 bg-muted/35 p-3"
                data-testid={`project-settings-access-grant-${grant.id}`}
              >
                <p className="font-medium text-foreground">{grant.principal_id}</p>
                <p className="text-xs text-muted-foreground">
                  {grant.principal_type} · role: {grant.role}
                </p>
              </div>
            ))}
            <div className="space-y-2 rounded-xl border border-panel-border/70 bg-muted/35 p-3">
              <Label htmlFor="project-settings-access-principal-id">Principal ID</Label>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                data-testid="project-settings-access-principal-id"
                id="project-settings-access-principal-id"
                onChange={(event) => setAccessPrincipalIdDraft(event.target.value)}
                placeholder="user@example.com"
                type="text"
                value={accessPrincipalIdDraft}
              />
              <div className="grid gap-2 sm:grid-cols-2">
                <label className="space-y-1 text-xs">
                  <span>Principal type</span>
                  <select
                    className="w-full rounded-md border border-input bg-background px-2 py-2 text-sm"
                    data-testid="project-settings-access-principal-type"
                    onChange={(event) =>
                      setAccessPrincipalTypeDraft(event.target.value as 'user' | 'service' | 'system')
                    }
                    value={accessPrincipalTypeDraft}
                  >
                    <option value="user">user</option>
                    <option value="service">service</option>
                    <option value="system">system</option>
                  </select>
                </label>
                <label className="space-y-1 text-xs">
                  <span>Role</span>
                  <select
                    className="w-full rounded-md border border-input bg-background px-2 py-2 text-sm"
                    data-testid="project-settings-access-role"
                    onChange={(event) => setAccessRoleDraft(event.target.value as 'owner' | 'editor' | 'viewer')}
                    value={accessRoleDraft}
                  >
                    <option value="owner">owner</option>
                    <option value="editor">editor</option>
                    <option value="viewer">viewer</option>
                  </select>
                </label>
              </div>
              <Button
                data-testid="project-settings-access-grant-submit"
                disabled={grantProjectAccessMutation.isMutating || accessPrincipalIdDraft.trim().length === 0}
                onClick={() => void handleGrantProjectAccess()}
                size="sm"
                type="button"
                variant="outline"
              >
                {grantProjectAccessMutation.isMutating ? 'Granting...' : 'Grant access'}
              </Button>
            </div>
          </CardContent>
        </Card>

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

        <Card data-testid="project-settings-providers-panel">
          <CardHeader>
            <CardTitle>Provider Status Management</CardTitle>
            <CardDescription>
              Manage global provider availability with `GET /api/llm/providers` and `PUT /api/llm/providers/:provider_name`.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            {llmProvidersQuery.isLoading ? (
              <p data-testid="project-settings-providers-loading">Loading provider statuses...</p>
            ) : null}
            {llmProvidersQuery.error ? (
              <p className="text-destructive" data-testid="project-settings-providers-error">
                {llmProvidersQuery.error.message}
              </p>
            ) : null}

            {(llmProvidersQuery.data?.providers ?? []).map((provider) => {
              const draftEnabled = providerEnabledDraftByName[provider.provider] ?? provider.enabled;
              const hasProviderUnsavedChange = draftEnabled !== provider.enabled;
              return (
                <div
                  key={provider.provider}
                  className="space-y-2 rounded-xl border border-panel-border/70 bg-muted/35 p-3"
                  data-testid={`project-settings-provider-row-${provider.provider}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium text-foreground">{provider.provider}</p>
                    <Switch
                      checked={draftEnabled}
                      data-testid={`project-settings-provider-toggle-${provider.provider}`}
                      disabled={updateLLMProviderStatusMutation.isMutating}
                      onCheckedChange={(nextEnabled) =>
                        setProviderEnabledDraftByName((previous) => ({
                          ...previous,
                          [provider.provider]: nextEnabled,
                        }))
                      }
                    />
                  </div>
                  <p data-testid={`project-settings-provider-current-${provider.provider}`}>
                    Current: <strong className="text-foreground">{provider.enabled ? 'enabled' : 'disabled'}</strong>{' '}
                    | Draft: <strong className="text-foreground">{draftEnabled ? 'enabled' : 'disabled'}</strong>
                  </p>
                  <Button
                    data-testid={`project-settings-provider-save-${provider.provider}`}
                    disabled={!hasProviderUnsavedChange || updateLLMProviderStatusMutation.isMutating}
                    onClick={() => void handleSaveProviderStatus(provider.provider)}
                    size="sm"
                    type="button"
                    variant="outline"
                  >
                    {updateLLMProviderStatusMutation.isMutating ? 'Saving...' : 'Save provider status'}
                  </Button>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>
    </WorkflowPageShell>
  );
}
