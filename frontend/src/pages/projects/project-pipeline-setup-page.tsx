import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import {
  useProjectLLMSettingsQuery,
  useLLMProvidersQuery,
  useUpdateProjectLLMSettingsMutation,
  useRunPipelineMutation,
  useModeCatalogQuery,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { runRequestSchema } from '@/app/schemas/api';
import type { RunRequestDto } from '@/app/schemas/api';

function SettingRow({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-6 border-b border-white/5 py-4 last:border-0">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{label}</p>
        {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

const DEFAULT_RUN_CONFIG = runRequestSchema.parse({
  mode: 'audiobook',
  max_segment_chars: 150,
  llm_enabled: true,
  provider_name: 'openai',
  max_calls_per_day: 500,
}) satisfies RunRequestDto;

export function ProjectPipelineSetupPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const selectedMode = useWorkspaceStore((state) => state.selectedMode);
  const setRunId = useWorkspaceStore((state) => state.setRunId);
  const projectId = routeProjectId ?? storeProjectId;

  const llmSettingsQuery = useProjectLLMSettingsQuery(projectId);
  const providersQuery = useLLMProvidersQuery(projectId !== null);
  const modeCatalogQuery = useModeCatalogQuery(projectId !== null);
  const updateLLMMutation = useUpdateProjectLLMSettingsMutation(projectId);
  const runMutation = useRunPipelineMutation(projectId);

  const providers = providersQuery.data?.providers ?? [];
  const llmEnabled = llmSettingsQuery.data?.llm_enabled ?? false;
  const effectiveMode = selectedMode ?? 'audiobook';
  const modeProfile = modeCatalogQuery.data?.mode_profiles?.[effectiveMode];
  const isBusy = updateLLMMutation.isMutating || runMutation.isMutating;

  async function handleToggleLLM() {
    if (!projectId) return;
    try {
      await updateLLMMutation.trigger({ llm_enabled: !llmEnabled });
      toast.success(`LLM ${!llmEnabled ? 'enabled' : 'disabled'}.`);
      await llmSettingsQuery.mutate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Update failed');
    }
  }

  async function handleRun() {
    if (!projectId) return;
    const firstEnabledProvider = providers.find((p) => p.enabled)?.provider ?? 'openai';
    const runConfig: RunRequestDto = {
      ...DEFAULT_RUN_CONFIG,
      mode: effectiveMode,
      llm_enabled: llmEnabled,
      provider_name: modeProfile?.provider_name ?? firstEnabledProvider,
      max_segment_chars: modeProfile?.max_segment_chars ?? DEFAULT_RUN_CONFIG.max_segment_chars,
      max_calls_per_day: modeProfile?.max_calls_per_day ?? DEFAULT_RUN_CONFIG.max_calls_per_day,
    };
    try {
      const result = await runMutation.trigger(runConfig);
      setRunId(result.run_id);
      toast.success(`Run #${result.run_id} started.`);
      navigate(`/projects/${projectId}/runs`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start run');
    }
  }

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Pipeline`}
      title="Pipeline Setup"
      description="Review configuration and trigger a new pipeline run."
    >
      <div className="max-w-2xl space-y-2">
        {/* Run Config Summary */}
        <div className="rounded-xl border border-white/10 bg-card px-5">
          <p className="pt-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">Run Configuration</p>
          <SettingRow label="Mode">
            <span className="text-sm font-medium capitalize text-foreground">{effectiveMode}</span>
          </SettingRow>
          {modeProfile && (
            <>
              <SettingRow label="Max segment chars">
                <span className="font-mono text-sm text-foreground">{modeProfile.max_segment_chars}</span>
              </SettingRow>
              <SettingRow label="Provider">
                <span className="text-sm text-foreground">{modeProfile.provider_name}</span>
              </SettingRow>
              <SettingRow label="Daily call cap">
                <span className="font-mono text-sm text-foreground">{modeProfile.max_calls_per_day}</span>
              </SettingRow>
            </>
          )}
        </div>

        {/* LLM Config */}
        <div className="rounded-xl border border-white/10 bg-card px-5">
          <p className="pt-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">LLM</p>
          <SettingRow
            label="LLM processing"
            description="Enable LLM-powered speaker and emotion tagging"
          >
            <button
              className="flex h-6 w-11 items-center rounded-full border border-white/20 bg-white/10 px-0.5 transition-colors data-[enabled=true]:border-green-400/40 data-[enabled=true]:bg-green-400/20"
              data-enabled={llmEnabled}
              disabled={isBusy}
              onClick={() => void handleToggleLLM()}
              type="button"
            >
              <span
                className="size-5 rounded-full bg-white/40 transition-transform data-[enabled=true]:translate-x-5 data-[enabled=true]:bg-green-400"
                data-enabled={llmEnabled}
              />
            </button>
          </SettingRow>
          {providers.length > 0 && (
            <SettingRow label="Providers">
              <div className="flex flex-wrap gap-1.5">
                {providers.map((p) => (
                  <span
                    className="inline-flex items-center gap-1 rounded-full border border-white/10 px-2 py-0.5 text-xs text-muted-foreground"
                    key={p.provider}
                  >
                    <span className={`size-1.5 rounded-full ${p.enabled ? 'bg-green-400' : 'bg-white/20'}`} />
                    {p.provider}
                  </span>
                ))}
              </div>
            </SettingRow>
          )}
        </div>

        {/* Start run */}
        <div className="flex items-center gap-3 pt-2">
          <Button
            data-testid="run-pipeline-button"
            disabled={isBusy}
            onClick={() => void handleRun()}
          >
            {runMutation.isMutating ? 'Starting…' : 'Start Run'}
          </Button>
          {!selectedMode && (
            <p className="text-xs text-muted-foreground">Select a mode in Mode Setup before running.</p>
          )}
        </div>
      </div>
    </WorkflowPageShell>
  );
}
