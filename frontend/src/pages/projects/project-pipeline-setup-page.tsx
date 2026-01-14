import { type FormEvent, useEffect, useMemo, useState } from 'react';

import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Mic2, Zap } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { NativeSelect } from '@/components/ui/native-select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Switch } from '@/components/ui/switch';
import {
  useCharacterMapQuery,
  useModeCatalogQuery,
  useRunPipelineMutation,
  useSaveVoicesMutation,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';

type InternalThoughtVoicePolicy = 'character' | 'narrator' | 'thought_voice';
type EmotionTaxonomy = 'basic' | 'expanded';

const DEFAULT_SPEAKER_CONFIDENCE_THRESHOLD = 0.6;
const DEFAULT_HIGH_AMBIGUITY_DIALOGUE_FLAG_THRESHOLD = 2;
const DEFAULT_UNSTABLE_EMOTION_SHIFT_TRANSITION_THRESHOLD = 4;
const DEFAULT_UNSTABLE_EMOTION_SHIFT_DENSITY_THRESHOLD = 0.5;
const DEFAULT_EXPORT_CHUNK_SIZE = 500;
const EXPORT_FORMAT_OPTIONS = ['json', 'csv', 'time_series_json', 'graph_json'] as const;

function normalizeExportFormats(formats: readonly unknown[]): string[] {
  const normalized = formats
    .map((format) => (typeof format === 'string' ? format.trim().toLowerCase() : ''))
    .filter((format) => format.length > 0);
  const deduped = Array.from(new Set(normalized));
  return deduped.filter((format) => EXPORT_FORMAT_OPTIONS.includes(format as (typeof EXPORT_FORMAT_OPTIONS)[number]));
}

function orderExportFormats(formats: readonly string[]): string[] {
  const deduped = new Set(formats);
  return EXPORT_FORMAT_OPTIONS.filter((format) => deduped.has(format));
}

function toggleExportFormat(formats: string[], format: string): string[] {
  const deduped = new Set(formats);
  if (deduped.has(format)) {
    if (deduped.size <= 1) {
      return orderExportFormats(formats);
    }
    deduped.delete(format);
  } else {
    deduped.add(format);
  }
  return orderExportFormats(Array.from(deduped));
}

type VoicePreviewRow = {
  speaker: string;
  resolvedVoice: string;
  rule: string;
  source: string;
};

function resolveNarrationFallbackVoice(params: {
  characterGender: string;
  explicitVoiceId: string;
  maleDefault: string;
  femaleDefault: string;
  neutralDefault: string;
  unknownDefault: string;
}) {
  const trimmedExplicitVoice = params.explicitVoiceId.trim();
  if (trimmedExplicitVoice) {
    return {
      voiceId: trimmedExplicitVoice,
      rule: 'explicit character override',
      source: 'character voice map',
    };
  }

  const normalizedGender = params.characterGender.trim().toLowerCase();
  if (normalizedGender === 'male') {
    return { voiceId: params.maleDefault, rule: 'gender fallback', source: 'male_default_voice' };
  }
  if (normalizedGender === 'female') {
    return { voiceId: params.femaleDefault, rule: 'gender fallback', source: 'female_default_voice' };
  }
  if (normalizedGender === 'neutral') {
    return { voiceId: params.neutralDefault, rule: 'gender fallback', source: 'neutral_default_voice' };
  }

  return { voiceId: params.unknownDefault, rule: 'gender fallback', source: 'unknown_default_voice' };
}

function resolveInternalThoughtPreviewVoice(params: {
  policy: InternalThoughtVoicePolicy;
  thoughtVoice: string;
  narratorVoice: string;
}) {
  if (params.policy === 'character') {
    return {
      voiceId: params.narratorVoice,
      source: 'character policy default',
      rule: 'uses resolved dialogue-style fallback',
    };
  }

  if (params.policy === 'thought_voice') {
    const normalizedThoughtVoice = params.thoughtVoice.trim();
    return {
      voiceId: normalizedThoughtVoice || params.narratorVoice,
      source: normalizedThoughtVoice ? 'custom thought_voice' : 'thought policy narrator fallback',
      rule: normalizedThoughtVoice ? 'thought_voice policy' : 'thought policy without override',
    };
  }

  return {
    voiceId: params.narratorVoice,
    source: 'internal thought policy',
    rule: 'narrator policy',
  };
}

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
  const [internalThoughtVoicePolicy, setInternalThoughtVoicePolicy] = useState<InternalThoughtVoicePolicy>('character');
  const [internalThoughtVoice, setInternalThoughtVoice] = useState('');
  const [maxSegmentChars, setMaxSegmentChars] = useState(255);
  const [llmEnabled, setLlmEnabled] = useState(false);
  const [deterministicMode, setDeterministicMode] = useState(false);
  const [webScrapingEnabled, setWebScrapingEnabled] = useState(false);
  const [emotionTaxonomy, setEmotionTaxonomy] = useState<EmotionTaxonomy>('basic');
  const [providerName, setProviderName] = useState('openrouter');
  const [maxCallsPerDay, setMaxCallsPerDay] = useState(25);
  const [exportFormats, setExportFormats] = useState<string[]>(Array.from(EXPORT_FORMAT_OPTIONS));
  const [exportChunkSize, setExportChunkSize] = useState(DEFAULT_EXPORT_CHUNK_SIZE);
  const [allowUnfinalizedCharacterMap, setAllowUnfinalizedCharacterMap] = useState(false);
  const [hasCustomMaxSegmentChars, setHasCustomMaxSegmentChars] = useState(false);
  const [hasCustomExportChunkSize, setHasCustomExportChunkSize] = useState(false);
  const [speakerConfidenceThreshold, setSpeakerConfidenceThreshold] = useState(DEFAULT_SPEAKER_CONFIDENCE_THRESHOLD);
  const [highAmbiguityDialogueFlagThreshold, setHighAmbiguityDialogueFlagThreshold] = useState(
    DEFAULT_HIGH_AMBIGUITY_DIALOGUE_FLAG_THRESHOLD,
  );
  const [unstableEmotionShiftTransitionThreshold, setUnstableEmotionShiftTransitionThreshold] = useState(
    DEFAULT_UNSTABLE_EMOTION_SHIFT_TRANSITION_THRESHOLD,
  );
  const [unstableEmotionShiftDensityThreshold, setUnstableEmotionShiftDensityThreshold] = useState(
    DEFAULT_UNSTABLE_EMOTION_SHIFT_DENSITY_THRESHOLD,
  );
  const [hasCustomSpeakerConfidenceThreshold, setHasCustomSpeakerConfidenceThreshold] = useState(false);
  const [hasCustomHighAmbiguityDialogueFlagThreshold, setHasCustomHighAmbiguityDialogueFlagThreshold] = useState(false);
  const [hasCustomUnstableEmotionShiftTransitionThreshold, setHasCustomUnstableEmotionShiftTransitionThreshold] = useState(
    false,
  );
  const [hasCustomUnstableEmotionShiftDensityThreshold, setHasCustomUnstableEmotionShiftDensityThreshold] = useState(false);
  const [contradictionReviewRequired, setContradictionReviewRequired] = useState(true);
  const [hasCustomContradictionReviewRequired, setHasCustomContradictionReviewRequired] = useState(false);

  const saveVoicesMutation = useSaveVoicesMutation(projectId);
  const runPipelineMutation = useRunPipelineMutation(projectId);
  const characterMapQuery = useCharacterMapQuery(projectId);
  const modeCatalogQuery = useModeCatalogQuery(projectId !== null);
  const isRunLocked = selectedMode === null;
  const hasUnfinalizedCharacterRows =
    characterMapQuery.data !== undefined && characterMapQuery.data.characters.length > 0 && !characterMapQuery.data.character_map_finalized;
  const runMode = selectedMode ?? modeCatalogQuery.data?.default_mode ?? null;
  const selectedProfile = runMode !== null ? modeCatalogQuery.data?.mode_profiles?.[runMode] : null;
  const characterRows = characterMapQuery.data?.characters ?? [];
  const voiceMappingPreviewRows: VoicePreviewRow[] = useMemo(() => {
    const resolvedCharacterRows = characterRows.map((character) => {
      const resolution = resolveNarrationFallbackVoice({
        characterGender: character.gender,
        explicitVoiceId: character.voice_id || '',
        maleDefault: maleVoice,
        femaleDefault: femaleVoice,
        neutralDefault: neutralVoice,
        unknownDefault: unknownVoice,
      });

      return {
        speaker: character.name,
        resolvedVoice: resolution.voiceId,
        rule: resolution.rule,
        source: resolution.source,
      };
    });

    return [
      {
        speaker: 'Narrator',
        resolvedVoice: narratorVoice,
        rule: 'explicit narrator default',
        source: 'narrator_voice',
      },
      ...resolvedCharacterRows,
    ];
  }, [characterRows, maleVoice, femaleVoice, neutralVoice, unknownVoice, narratorVoice]);
  const internalThoughtPreview = useMemo(
    () =>
      resolveInternalThoughtPreviewVoice({
        policy: internalThoughtVoicePolicy,
        thoughtVoice: internalThoughtVoice,
        narratorVoice,
      }),
    [internalThoughtVoicePolicy, internalThoughtVoice, narratorVoice],
  );

  useEffect(() => {
    if (selectedProfile !== null && selectedProfile !== undefined) {
      setWebScrapingEnabled(Boolean(selectedProfile.web_scraping_enabled));
    }
  }, [selectedProfile]);

  useEffect(() => {
    setHasCustomMaxSegmentChars(false);
    setHasCustomExportChunkSize(false);
    setHasCustomSpeakerConfidenceThreshold(false);
    setHasCustomHighAmbiguityDialogueFlagThreshold(false);
    setHasCustomUnstableEmotionShiftTransitionThreshold(false);
    setHasCustomUnstableEmotionShiftDensityThreshold(false);
    setHasCustomContradictionReviewRequired(false);
    setExportFormats(Array.from(EXPORT_FORMAT_OPTIONS));
  }, [runMode]);

  useEffect(() => {
    if (!hasCustomMaxSegmentChars && selectedProfile !== null && selectedProfile !== undefined) {
      setMaxSegmentChars(selectedProfile.max_segment_chars);
    }
  }, [hasCustomMaxSegmentChars, selectedProfile]);

  useEffect(() => {
    if (!hasCustomExportChunkSize && selectedProfile !== null && selectedProfile !== undefined) {
      setExportChunkSize(selectedProfile.export_chunk_size ?? DEFAULT_EXPORT_CHUNK_SIZE);
    }
  }, [hasCustomExportChunkSize, selectedProfile]);

  useEffect(() => {
    if (!hasCustomSpeakerConfidenceThreshold && selectedProfile !== null && selectedProfile !== undefined) {
      setSpeakerConfidenceThreshold(selectedProfile.speaker_confidence_threshold ?? DEFAULT_SPEAKER_CONFIDENCE_THRESHOLD);
    }
  }, [hasCustomSpeakerConfidenceThreshold, selectedProfile]);

  useEffect(() => {
    if (
      !hasCustomHighAmbiguityDialogueFlagThreshold &&
      selectedProfile !== null &&
      selectedProfile !== undefined
    ) {
      setHighAmbiguityDialogueFlagThreshold(
        selectedProfile.high_ambiguity_dialogue_flag_threshold ??
          DEFAULT_HIGH_AMBIGUITY_DIALOGUE_FLAG_THRESHOLD,
      );
    }
  }, [hasCustomHighAmbiguityDialogueFlagThreshold, selectedProfile]);

  useEffect(() => {
    if (
      !hasCustomUnstableEmotionShiftTransitionThreshold &&
      selectedProfile !== null &&
      selectedProfile !== undefined
    ) {
      setUnstableEmotionShiftTransitionThreshold(
        selectedProfile.unstable_emotion_shift_transition_threshold ??
          DEFAULT_UNSTABLE_EMOTION_SHIFT_TRANSITION_THRESHOLD,
      );
    }
  }, [hasCustomUnstableEmotionShiftTransitionThreshold, selectedProfile]);

  useEffect(() => {
    if (
      !hasCustomUnstableEmotionShiftDensityThreshold &&
      selectedProfile !== null &&
      selectedProfile !== undefined
    ) {
      setUnstableEmotionShiftDensityThreshold(
        selectedProfile.unstable_emotion_shift_density_threshold ??
          DEFAULT_UNSTABLE_EMOTION_SHIFT_DENSITY_THRESHOLD,
      );
    }
  }, [hasCustomUnstableEmotionShiftDensityThreshold, selectedProfile]);

  useEffect(() => {
    if (
      !hasCustomContradictionReviewRequired &&
      selectedProfile !== null &&
      selectedProfile !== undefined
    ) {
      setContradictionReviewRequired(
        selectedProfile.contradiction_review_required !== undefined
          ? selectedProfile.contradiction_review_required
          : true,
      );
    }
  }, [hasCustomContradictionReviewRequired, selectedProfile]);

  useEffect(() => {
    if (selectedProfile === null || selectedProfile === undefined) {
      return;
    }

    const profileFormats = normalizeExportFormats(Array.isArray(selectedProfile.export_formats) ? selectedProfile.export_formats : []);
    setExportFormats(profileFormats.length > 0 ? profileFormats : Array.from(EXPORT_FORMAT_OPTIONS));
  }, [selectedProfile]);

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
        export_chunk_size: exportChunkSize,
        speaker_confidence_threshold: speakerConfidenceThreshold,
        high_ambiguity_dialogue_flag_threshold: highAmbiguityDialogueFlagThreshold,
        unstable_emotion_shift_transition_threshold: unstableEmotionShiftTransitionThreshold,
        unstable_emotion_shift_density_threshold: unstableEmotionShiftDensityThreshold,
        export_formats: exportFormats,
        contradiction_review_required: contradictionReviewRequired,
        deterministic_mode: deterministicMode,
        web_scraping_enabled: webScrapingEnabled,
        emotion_taxonomy: emotionTaxonomy,
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
                  onChange={(event) =>
                    setInternalThoughtVoicePolicy(
                      event.target.value as InternalThoughtVoicePolicy,
                    )
                  }
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
    <div className="rounded-lg border border-border/60 bg-muted/30 px-3 py-2">
                <p className="text-sm font-medium">Voice fallback preview</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Check how current defaults resolve before saving voice settings.
                </p>
                <div className="mt-2 overflow-x-auto">
                  <Table data-testid="voice-mapping-preview-table">
                    <TableHeader>
                      <TableRow>
                        <TableHead>Speaker</TableHead>
                        <TableHead>Resolved voice</TableHead>
                        <TableHead>Rule</TableHead>
                        <TableHead>Source</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {voiceMappingPreviewRows.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={4} className="text-sm text-muted-foreground">
                            No character map entries found yet.
                          </TableCell>
                        </TableRow>
                      ) : (
                        voiceMappingPreviewRows.map((row, index) => (
                          <TableRow key={`${row.speaker}-${row.source}-${index}`} data-testid="voice-mapping-preview-row">
                            <TableCell className="font-medium">{row.speaker}</TableCell>
                            <TableCell>{row.resolvedVoice}</TableCell>
                            <TableCell>{row.rule}</TableCell>
                            <TableCell>{row.source}</TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
                <p className="mt-3 text-sm" data-testid="internal-thought-preview">
                  Internal-thought preview:{' '}
                  <span className="font-medium">{internalThoughtPreview.voiceId}</span>
                  <span className="ml-2 text-xs text-muted-foreground">({internalThoughtPreview.rule})</span>
                </p>
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
                <Label>Export formats</Label>
                <div className="grid gap-2 rounded-lg border border-border/60 bg-muted/30 px-3 py-2">
                  {EXPORT_FORMAT_OPTIONS.map((format) => (
                    <label
                      key={format}
                      htmlFor={`export-format-${format}`}
                      className="inline-flex items-center gap-2 text-sm"
                    >
                      <Checkbox
                        id={`export-format-${format}`}
                        checked={exportFormats.includes(format)}
                        disabled={exportFormats.length === 1 && exportFormats.includes(format)}
                        onCheckedChange={() =>
                          setExportFormats((previousFormats) => toggleExportFormat(previousFormats, format))
                        }
                      />
                      <span className="font-medium uppercase">{format}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="max-segment-chars">Segmentation target length</Label>
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
                <Label htmlFor="export-chunk-size">Export chunk size</Label>
                <Input
                  id="export-chunk-size"
                  min={1}
                  max={10000}
                  type="number"
                  value={exportChunkSize}
                  onChange={(event) => {
                    setHasCustomExportChunkSize(true);
                    setExportChunkSize(Number(event.target.value));
                  }}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="speaker-confidence-threshold">Speaker confidence threshold</Label>
                <Input
                  id="speaker-confidence-threshold"
                  min={0}
                  max={1}
                  step={0.01}
                  type="number"
                  value={speakerConfidenceThreshold}
                  onChange={(event) => {
                    setHasCustomSpeakerConfidenceThreshold(true);
                    setSpeakerConfidenceThreshold(Number(event.target.value));
                  }}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="high-ambiguity-dialogue-flag-threshold">
                  High-ambiguity dialogue flag threshold
                </Label>
                <Input
                  id="high-ambiguity-dialogue-flag-threshold"
                  min={1}
                  max={20}
                  type="number"
                  value={highAmbiguityDialogueFlagThreshold}
                  onChange={(event) => {
                    setHasCustomHighAmbiguityDialogueFlagThreshold(true);
                    setHighAmbiguityDialogueFlagThreshold(Number(event.target.value));
                  }}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="unstable-emotion-shift-transition-threshold">
                  Unstable emotion transition threshold
                </Label>
                <Input
                  id="unstable-emotion-shift-transition-threshold"
                  min={1}
                  max={20}
                  type="number"
                  value={unstableEmotionShiftTransitionThreshold}
                  onChange={(event) => {
                    setHasCustomUnstableEmotionShiftTransitionThreshold(true);
                    setUnstableEmotionShiftTransitionThreshold(Number(event.target.value));
                  }}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="unstable-emotion-shift-density-threshold">
                  Unstable emotion shift density threshold
                </Label>
                <Input
                  id="unstable-emotion-shift-density-threshold"
                  min={0}
                  max={1}
                  step={0.01}
                  type="number"
                  value={unstableEmotionShiftDensityThreshold}
                  onChange={(event) => {
                    setHasCustomUnstableEmotionShiftDensityThreshold(true);
                    setUnstableEmotionShiftDensityThreshold(Number(event.target.value));
                  }}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="emotion-taxonomy">Emotion taxonomy</Label>
                <NativeSelect
                  id="emotion-taxonomy"
                  value={emotionTaxonomy}
                  onChange={(event) => setEmotionTaxonomy(event.target.value as EmotionTaxonomy)}
                >
                  <option value="basic">Basic</option>
                  <option value="expanded">Expanded</option>
                </NativeSelect>
              </div>
              <label className="inline-flex items-center justify-between gap-2 rounded-xl bg-background/70 px-3 py-2 text-sm">
                <span>Review contradictions before export</span>
                <Switch
                  checked={contradictionReviewRequired}
                  onCheckedChange={(value) => {
                    setHasCustomContradictionReviewRequired(true);
                    setContradictionReviewRequired(value);
                  }}
                />
              </label>
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
                <span>Enable deterministic mode</span>
                <Switch checked={deterministicMode} onCheckedChange={setDeterministicMode} />
              </label>
              <label className="inline-flex items-center justify-between gap-2 rounded-xl bg-background/70 px-3 py-2 text-sm">
                <span>Enable web scraping</span>
                <Switch checked={webScrapingEnabled} onCheckedChange={setWebScrapingEnabled} />
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
