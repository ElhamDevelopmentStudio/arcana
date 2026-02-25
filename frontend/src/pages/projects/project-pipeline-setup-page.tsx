import { type FormEvent, useState } from 'react';

import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import { useRunPipelineMutation, useSaveVoicesMutation } from '@/features/workflow/api/workflow-hooks';
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
  const [maxSegmentChars, setMaxSegmentChars] = useState(255);
  const [llmEnabled, setLlmEnabled] = useState(false);
  const [providerName, setProviderName] = useState('openrouter');
  const [maxCallsPerDay, setMaxCallsPerDay] = useState(25);

  const saveVoicesMutation = useSaveVoicesMutation(projectId);
  const runPipelineMutation = useRunPipelineMutation(projectId);
  const isRunLocked = selectedMode === null;

  async function handleSaveVoices(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }

    try {
      await saveVoicesMutation.trigger({
        narrator_voice: narratorVoice,
        male_default_voice: maleVoice,
        female_default_voice: femaleVoice,
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
      const run = await runPipelineMutation.trigger({
        mode: selectedMode,
        max_segment_chars: maxSegmentChars,
        llm_enabled: llmEnabled,
        provider_name: providerName,
        max_calls_per_day: maxCallsPerDay,
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
      action={projectId !== null ? <Badge variant="outline">Project #{projectId}</Badge> : <Badge variant="outline">Project required</Badge>}
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Voice and Segmentation Config</CardTitle>
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
              <Button disabled={saveVoicesMutation.isMutating || projectId === null} type="submit">
                {saveVoicesMutation.isMutating ? 'Saving...' : 'Save Voice Config'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Run Trigger</CardTitle>
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
                  min={64}
                  max={1000}
                  type="number"
                  value={maxSegmentChars}
                  onChange={(event) => setMaxSegmentChars(Number(event.target.value))}
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
              <label className="inline-flex items-center gap-2 text-sm">
                <input checked={llmEnabled} onChange={(event) => setLlmEnabled(event.target.checked)} type="checkbox" />
                Enable LLM-assisted refinement
              </label>
              <Button
                data-testid="run-pipeline-button"
                disabled={runPipelineMutation.isMutating || projectId === null || isRunLocked}
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
