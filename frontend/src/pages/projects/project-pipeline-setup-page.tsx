import { type FormEvent, useEffect, useState } from 'react';

import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Mic2, Zap } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import { Switch } from '@/components/ui/switch';
import {
  useCharacterMapQuery,
  useModeCatalogQuery,
  useRunPipelineMutation,
  useSaveVoicesMutation,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';

export function ProjectPipelineSetupPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const selectedMode = useWorkspaceStore((state) => state.selectedMode);
  const setRunId = useWorkspaceStore((state) => state.setRunId);

  const projectId = routeProjectId ?? storeProjectId;

  const [narratorVoice, setNarratorVoice] = useState('narrator_default');
  const [maleVoice, setMaleVoice] = useState('male_default');
  const [femaleVoice, setFemaleVoice] = useState('female_default');
  const [neutralVoice, setNeutralVoice] = useState('neutral_default');
  const [unknownVoice, setUnknownVoice] = useState('unknown_default');
  const [internalThoughtVoicePolicy, setInternalThoughtVoicePolicy] = useState('character');
  const [internalThoughtVoice, setInternalThoughtVoice] = useState('');
  const [maxSegmentChars, setMaxSegmentChars] = useState(255);
  const [llmEnabled, setLlmEnabled] = useState(false);
  const [providerName, setProviderName] = useState('openrouter');
  const [maxCallsPerDay, setMaxCallsPerDay] = useState(25);
  const [allowUnfinalizedCharacterMap, setAllowUnfinalizedCharacterMap] = useState(false);
  const [hasCustomMaxSegmentChars, setHasCustomMaxSegmentChars] = useState(false);

  const saveVoicesMutation = useSaveVoicesMutation(projectId);
  const runPipelineMutation = useRunPipelineMutation(projectId);
  const characterMapQuery = useCharacterMapQuery(projectId);
  const modeCatalogQuery = useModeCatalogQuery(projectId !== null);
  const isRunLocked = selectedMode === null;
  const hasUnfinalizedCharacterRows =
    characterMapQuery.data !== undefined && characterMapQuery.data.characters.length > 0 && !characterMapQuery.data.character_map_finalized;
  const runMode = selectedMode ?? modeCatalogQuery.data?.default_mode ?? null;
  const selectedProfile = runMode !== null ? modeCatalogQuery.data?.mode_profiles?.[runMode] : null;

  useEffect(() => {
    setHasCustomMaxSegmentChars(false);
  }, [runMode]);

  useEffect(() => {
    if (!hasCustomMaxSegmentChars && selectedProfile !== null && selectedProfile !== undefined) {
      setMaxSegmentChars(selectedProfile.max_segment_chars);
    }
  }, [hasCustomMaxSegmentChars, selectedProfile]);

  async function handleSaveVoices(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }

    try {
      const trimmedThoughtVoice =
        internalThoughtVoicePolicy === 'thought_voice' ? internalThoughtVoice.trim() : '';

      await saveVoicesMutation.trigger({
        narrator_voice: narratorVoice,
        male_default_voice: maleVoice,
        female_default_voice: femaleVoice,
        neutral_default_voice: neutralVoice,
        unknown_default_voice: unknownVoice,
        internal_thought_voice_policy: internalThoughtVoicePolicy,
        internal_thought_voice: trimmedThoughtVoice || undefined,
      });
      toast.success('Voice configuration saved.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save voices');
    }
  }

  async function handleRunPipeline(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    if (selectedMode === null) {
      toast.error('Select a mode before running the pipeline.');
      return;
    }

    try {
      const trimmedThoughtVoice =
        internalThoughtVoicePolicy === 'thought_voice' ? internalThoughtVoice.trim() : '';

      const run = await runPipelineMutation.trigger({
        mode: selectedMode,
        max_segment_chars: maxSegmentChars,
        llm_enabled: llmEnabled,
        provider_name: providerName,
        max_calls_per_day: maxCallsPerDay,
        allow_unfinalized_character_map: allowUnfinalizedCharacterMap,
        internal_thought_voice_policy: internalThoughtVoicePolicy,
        internal_thought_voice: trimmedThoughtVoice || undefined,
      });
      setRunId(run.run_id);
      toast.success(`Run #${run.run_id} completed with ${run.segment_count} segments.`);
      navigate(projectRoute(projectId, 'run-monitor'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Pipeline run failed.');
    }
  }

  return (
    <WorkflowPageShell
      step="Step 04"
      title="Pipeline Setup"
      description="Configure run settings and trigger execution. This page owns run configuration only."
      action={
        <p className="text-sm text-muted-foreground">{projectId !== null ? `Project #${projectId}` : 'Project required'}</p>
      }
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mic2 className="size-4 text-primary" />
              Voice and Segmentation Config
            </CardTitle>
            <CardDescription>Defaults used for downstream voice mapping and segment generation.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-3" onSubmit={handleSaveVoices}>
              <div className="grid gap-2">
                <Label htmlFor="narrator-voice">Narrator voice</Label>
                <Input id="narrator-voice" value={narratorVoice} onChange={(event) => setNarratorVoice(event.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="male-voice">Default male voice</Label>
                <Input id="male-voice" value={maleVoice} onChange={(event) => setMaleVoice(event.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="female-voice">Default female voice</Label>
                <Input id="female-voice" value={femaleVoice} onChange={(event) => setFemaleVoice(event.target.value)} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="neutral-voice">Default neutral voice</Label>
                <Input
                  id="neutral-voice"
                  value={neutralVoice}
                  onChange={(event) => setNeutralVoice(event.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="unknown-voice">Default unknown voice</Label>
                <Input
                  id="unknown-voice"
                  value={unknownVoice}
                  onChange={(event) => setUnknownVoice(event.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="internal-thought-policy">Internal thought voice policy</Label>
                <NativeSelect
                  id="internal-thought-policy"
                  value={internalThoughtVoicePolicy}
                  onChange={(event) => setInternalThoughtVoicePolicy(event.target.value)}
                >
                  <option value="character">Use character voice</option>
                  <option value="narrator">Use narrator voice</option>
                  <option value="thought_voice">Use separate thought voice</option>
                </NativeSelect>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="internal-thought-voice">Thought voice</Label>
                <Input
                  id="internal-thought-voice"
                  value={internalThoughtVoice}
                  onChange={(event) => setInternalThoughtVoice(event.target.value)}
                  disabled={internalThoughtVoicePolicy !== 'thought_voice'}
                  placeholder="Only required when using thought voice policy"
                />
              </div>
              <Button disabled={saveVoicesMutation.isMutating || projectId === null} type="submit">
                {saveVoicesMutation.isMutating ? 'Saving...' : 'Save Voice Config'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="size-4 text-primary" />
              Run Trigger
            </CardTitle>
            <CardDescription>Run mode snapshot and execution controls for the current project.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-3" onSubmit={handleRunPipeline}>
              <div className="grid gap-2">
                <Label htmlFor="run-mode">Selected mode</Label>
                <Input id="run-mode" disabled value={selectedMode ?? 'not selected'} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="max-segment-chars">Max segment chars</Label>
                <Input
                  id="max-segment-chars"
                  min={80}
                  max={255}
                  type="number"
                  value={maxSegmentChars}
                  onChange={(event) => {
                    setHasCustomMaxSegmentChars(true);
                    setMaxSegmentChars(Number(event.target.value));
                  }}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="provider-name">Provider</Label>
                <NativeSelect id="provider-name" value={providerName} onChange={(event) => setProviderName(event.target.value)}>
                  <option value="openrouter">openrouter</option>
                  <option value="siliconflow">siliconflow (placeholder)</option>
                  <option value="groq">groq (placeholder)</option>
                </NativeSelect>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="max-calls">Max calls per day</Label>
                <Input
                  id="max-calls"
                  min={1}
                  type="number"
                  value={maxCallsPerDay}
                  onChange={(event) => setMaxCallsPerDay(Number(event.target.value))}
                />
              </div>
              <label className="inline-flex items-center justify-between gap-2 rounded-xl bg-background/70 px-3 py-2 text-sm">
                <span>Enable LLM-assisted refinement</span>
                <Switch checked={llmEnabled} onCheckedChange={setLlmEnabled} />
              </label>
              <label className="inline-flex items-center justify-between gap-2 rounded-xl bg-background/70 px-3 py-2 text-sm">
                <span>Run with unfinalized character map</span>
                <Switch
                  checked={allowUnfinalizedCharacterMap}
                  onCheckedChange={setAllowUnfinalizedCharacterMap}
                  disabled={!hasUnfinalizedCharacterRows}
                />
              </label>
              {hasUnfinalizedCharacterRows ? (
                <p className="text-sm text-muted-foreground">
                  This project has an unfinalized character map. Enable override only when you want to proceed with proposed names.
                </p>
              ) : null}
              <Button
                data-testid="run-pipeline-button"
                disabled={runPipelineMutation.isMutating || projectId === null || isRunLocked || hasUnfinalizedCharacterRows && !allowUnfinalizedCharacterMap}
                type="submit"
              >
                {runPipelineMutation.isMutating ? 'Running...' : 'Run Pipeline'}
              </Button>
              {isRunLocked ? (
                <p className="text-sm text-muted-foreground" data-testid="mode-lock-hint">
                  Return to the mode page and make an explicit mode selection before running.
                </p>
              ) : null}
            </form>
          </CardContent>
        </Card>
      </div>
    </WorkflowPageShell>
  );
}
