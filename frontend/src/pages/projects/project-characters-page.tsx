import { type FormEvent, useEffect, useMemo, useState } from 'react';

import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { AlertCircle, FileUp, Plus, Search, UserCog, WandSparkles } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { appEnv } from '@/app/config/env';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import type {
  CharacterExtractionDto,
  CharacterMapDto,
  PronunciationDictionaryPreviewRequestDto,
  PronunciationDictionaryPreviewResponseDto,
} from '@/app/schemas/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import { Textarea } from '@/components/ui/textarea';
import {
  useAutoExtractCharactersMutation,
  useCharacterMapQuery,
  useCharacterGenderComparisonQuery,
  useScrapeCharactersMutation,
  useMergeCharactersMutation,
  useInferCharacterGendersMutation,
  useImportCharactersMutation,
  useSaveCharacterMapMutation,
  useFinalizeCharacterMapMutation,
  usePronunciationPreviewMutation,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { Checkbox } from '@/components/ui/checkbox';

const STANDARD_GENDERS = new Set(['male', 'female', 'neutral']);
const SCRAPE_LEGAL_WARNING_TEXT =
  'Only use web-scrape sources you are legally authorized to access. External sources may include inaccurate data and may be restricted by terms of service or copyright.';

function normalizeCharacterName(value: string): string {
  return value.trim().toLowerCase();
}

function normalizeGender(value: string | null | undefined): string {
  if (typeof value !== 'string') {
    return 'unknown';
  }
  return value.trim().toLowerCase() || 'unknown';
}

function isGenderContradiction(manualGender: string, inferredGender: string): boolean {
  const normalizedManual = normalizeGender(manualGender);
  const normalizedInferred = normalizeGender(inferredGender);

  if (!STANDARD_GENDERS.has(normalizedManual) || !STANDARD_GENDERS.has(normalizedInferred)) {
    return false;
  }

  return normalizedManual !== normalizedInferred;
}

type ManualCharacterRow = {
  id: string;
  name: string;
  verbalized: string;
  gender: string;
  aliases: string;
  inferredGender: string;
};

type ManualCharacterRowError = {
  name?: string;
  verbalized?: string;
};

type CharacterMergeUndoEntry = {
  previousManualRows: ManualCharacterRow[];
  previousMergeSuggestions: CharacterExtractionDto['canonical_merge_suggestions'];
  canonicalName: string;
  aliasName: string;
};

function createRow(): ManualCharacterRow {
  return {
    id: crypto.randomUUID(),
    name: '',
    verbalized: '',
    gender: 'unknown',
    aliases: '',
    inferredGender: 'unknown',
  };
}

function toManualRows(map: CharacterMapDto | undefined): ManualCharacterRow[] {
  if (!map?.characters.length) {
    return [createRow()];
  }

  return map.characters.map((item) => ({
    id: crypto.randomUUID(),
    name: item.name,
    verbalized: item.verbalized_form,
    gender: item.gender,
    aliases: item.aliases.join(', '),
    inferredGender: item.inferred_gender,
  }));
}

function parseAliases(rawAliases: string): string[] {
  const normalized = rawAliases
    .split(',')
    .map((alias) => alias.trim())
    .filter(Boolean);
  return [...new Set(normalized)];
}

function mergeManualRows(
  rows: ManualCharacterRow[],
  canonicalName: string,
  aliasName: string,
): ManualCharacterRow[] | null {
  const canonicalIndex = rows.findIndex(
    (row) => normalizeCharacterName(row.name) === normalizeCharacterName(canonicalName),
  );
  const aliasIndex = rows.findIndex((row) => normalizeCharacterName(row.name) === normalizeCharacterName(aliasName));

  if (canonicalIndex < 0 || aliasIndex < 0 || canonicalIndex === aliasIndex) {
    return null;
  }

  const canonicalRow = rows[canonicalIndex];
  const aliasRow = rows[aliasIndex];

  const aliasSet = new Set([...parseAliases(canonicalRow.aliases), aliasRow.name.trim(), ...parseAliases(aliasRow.aliases)]);
  aliasSet.delete(canonicalRow.name.trim());

  const mergedCanonicalRow: ManualCharacterRow = {
    ...canonicalRow,
    aliases: [...aliasSet].join(', '),
  };

  const nextRows = rows.filter((_, index) => index !== aliasIndex);
  const canonicalAdjustedIndex = canonicalIndex > aliasIndex ? canonicalIndex - 1 : canonicalIndex;
  nextRows[canonicalAdjustedIndex] = mergedCanonicalRow;
  return nextRows;
}

export function ProjectCharactersPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;

  const importCharactersMutation = useImportCharactersMutation(projectId);
  const [characterFile, setCharacterFile] = useState<File | null>(null);
  const [importedCount, setImportedCount] = useState<number | null>(null);
  const [lastSavedCount, setLastSavedCount] = useState<number | null>(null);
  const [autoExtractedCandidates, setAutoExtractedCandidates] = useState<CharacterMapDto['characters']>([]);
  const [scrapeUrl, setScrapeUrl] = useState<string>('');
  const [scrapeWarningAcknowledged, setScrapeWarningAcknowledged] = useState<boolean>(false);
  const [scrapedCandidates, setScrapedCandidates] = useState<CharacterMapDto['characters']>([]);
  const [mergeCandidates, setMergeCandidates] = useState<CharacterMapDto['characters']>([]);
  const [proposedCandidates, setProposedCandidates] = useState<CharacterMapDto['characters']>([]);
  const [mergeSuggestions, setMergeSuggestions] = useState<CharacterExtractionDto['canonical_merge_suggestions']>([]);
  const [characterExtractionWarnings, setCharacterExtractionWarnings] = useState<CharacterExtractionDto['warnings']>([]);
  const [mergeUndoHistory, setMergeUndoHistory] = useState<CharacterMergeUndoEntry[]>([]);
  const [mergeScrapeUrl, setMergeScrapeUrl] = useState<string>('');
  const [mergeScrapeAcknowledged, setMergeScrapeAcknowledged] = useState<boolean>(false);
  const [pronunciationPreviewText, setPronunciationPreviewText] = useState<string>('');
  const [includeGlobalPronunciationScope, setIncludeGlobalPronunciationScope] = useState<boolean>(true);
  const [includeCharacterPronunciationScope, setIncludeCharacterPronunciationScope] = useState<boolean>(false);
  const [includePlacePronunciationScope, setIncludePlacePronunciationScope] = useState<boolean>(false);
  const [includeArtifactPronunciationScope, setIncludeArtifactPronunciationScope] = useState<boolean>(false);
  const [includeInventedPronunciationScope, setIncludeInventedPronunciationScope] = useState<boolean>(false);
  const [pronunciationMatchWholeWords, setPronunciationMatchWholeWords] = useState<boolean>(true);
  const [pronunciationCaseSensitive, setPronunciationCaseSensitive] = useState<boolean>(true);
  const [pronunciationAliasAware, setPronunciationAliasAware] = useState<boolean>(false);
  const [pronunciationPreviewCharacterName, setPronunciationPreviewCharacterName] = useState<string>('');
  const [pronunciationPreviewResult, setPronunciationPreviewResult] = useState<
    PronunciationDictionaryPreviewResponseDto | null
  >(null);

  const characterMapQuery = useCharacterMapQuery(projectId);
  const characterGenderComparisonQuery = useCharacterGenderComparisonQuery(projectId);
  const [manualRows, setManualRows] = useState<ManualCharacterRow[]>([createRow()]);
  const genderComparisonRows = useMemo(() => {
    const mapped: Record<string, string> = {};

    for (const comparison of characterGenderComparisonQuery.data?.comparisons ?? []) {
      const name = comparison.name.trim().toLowerCase();
      if (!name) {
        continue;
      }
      mapped[name] = comparison.inferred_gender;
    }
    return mapped;
  }, [characterGenderComparisonQuery.data]);
  const genderContradictionRows = useMemo(() => {
    return manualRows.reduce<string[]>((acc, row) => {
      const rowName = row.name.trim();
      if (!rowName) {
        return acc;
      }
      const inferredGender = genderComparisonRows[rowName.toLowerCase()] ?? row.inferredGender;

      if (!isGenderContradiction(row.gender, inferredGender)) {
        return acc;
      }
      acc.push(rowName);
      return acc;
    }, []);
  }, [manualRows, genderComparisonRows]);
  const manualRowErrors = useMemo<Record<string, ManualCharacterRowError>>(() => {
    return manualRows.reduce<Record<string, ManualCharacterRowError>>((acc, row) => {
      const hasName = row.name.trim().length > 0;
      const hasVerbalized = row.verbalized.trim().length > 0;
      const hasAnyValue = hasName || hasVerbalized;

      if (!hasAnyValue) {
        return acc;
      }

      const next = { ...acc };
      if (!hasName) {
        next[row.id] = { ...next[row.id], name: 'Character name is required.' };
      }
      if (!hasVerbalized) {
        next[row.id] = { ...next[row.id], verbalized: 'Verbalized form is required.' };
      }
      return next;
    }, {});
  }, [manualRows]);
  const hasManualRowErrors = useMemo<boolean>(() => Object.keys(manualRowErrors).length > 0, [manualRowErrors]);
  const manualPreviewCount = useMemo(
    () => manualRows.filter((row) => row.name.trim() && row.verbalized.trim()).length,
    [manualRows],
  );
  const aliasCollisionWarnings = useMemo(
    () => (characterExtractionWarnings ?? []).filter((warning) => warning.type === 'ambiguous_alias_collision'),
    [characterExtractionWarnings],
  );
  const lowConfidenceWarnings = useMemo(
    () => (characterExtractionWarnings ?? []).filter((warning) => warning.type === 'low_confidence_character_candidate'),
    [characterExtractionWarnings],
  );
  const characterNameOptions = useMemo(() => {
    if (!characterMapQuery.data) {
      return [];
    }
    return characterMapQuery.data.characters
      .map((character) => character.name.trim())
      .filter(Boolean)
      .filter((name, index, allNames) => allNames.indexOf(name) === index)
      .sort((a, b) => a.localeCompare(b));
  }, [characterMapQuery.data]);

  const saveCharactersMutation = useSaveCharacterMapMutation(projectId);
  const autoExtractCharactersMutation = useAutoExtractCharactersMutation(projectId);
  const scrapeCharactersMutation = useScrapeCharactersMutation(projectId);
  const mergeCharactersMutation = useMergeCharactersMutation(projectId);
  const inferCharacterGendersMutation = useInferCharacterGendersMutation(projectId);
  const finalizeCharactersMutation = useFinalizeCharacterMapMutation(projectId);
  const pronunciationPreviewMutation = usePronunciationPreviewMutation(projectId);
  const isCharacterMapFinalized = characterMapQuery.data?.character_map_finalized ?? false;

  useEffect(() => {
    if (characterMapQuery.data === undefined) {
      return;
    }
    setManualRows(toManualRows(characterMapQuery.data));
    setMergeUndoHistory([]);
  }, [characterMapQuery.data]);

  useEffect(() => {
    if (characterMapQuery.data && lastSavedCount === null) {
      setLastSavedCount(characterMapQuery.data.characters.length);
    }
  }, [characterMapQuery.data, lastSavedCount]);

  async function handleImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    if (!characterFile) {
      toast.error('Select a CSV/JSON file first.');
      return;
    }

    try {
      const payload = await importCharactersMutation.trigger({ file: characterFile });
      setImportedCount(payload.imported_count);
      await characterMapQuery.mutate();
      toast.success(`Imported ${payload.imported_count} character rows.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Character import failed.');
    }
  }

  async function handleSaveManualCharacters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    if (hasManualRowErrors) {
      toast.error('Fix inline validation errors before saving.');
      return;
    }

    const payloadCharacters = manualRows
      .map((row) => ({
        name: row.name.trim(),
        verbalized_form: row.verbalized.trim(),
        gender: row.gender.trim().toLowerCase() as CharacterMapDto['characters'][number]['gender'],
        aliases: parseAliases(row.aliases),
      }))
      .filter((row) => row.name && row.verbalized_form)
      .map((row) => ({
        ...row,
        notes: null,
        source_trace: [],
        source: 'manual',
        confidence: 1.0,
      }));

    try {
      const savedMap = await saveCharactersMutation.trigger({ characters: payloadCharacters });
      setLastSavedCount(savedMap.characters.length);
      setManualRows(toManualRows(savedMap));
      toast.success(`Saved ${savedMap.characters.length} character rows.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to save character map.');
    }
  }

  async function handleAutoExtract(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }

    try {
      const payload = await autoExtractCharactersMutation.trigger();
      setAutoExtractedCandidates(payload.candidates);
      setCharacterExtractionWarnings(payload.warnings ?? []);
      toast.success(`Auto-extracted ${payload.candidate_count} character candidates.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Character auto-extraction failed.');
    }
  }

  async function handleScrapeCharacters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    if (!scrapeUrl.trim()) {
      toast.error('Add a source URL first.');
      return;
    }
    if (!scrapeWarningAcknowledged) {
      toast.error('Acknowledge the scrape warning to continue.');
      return;
    }

    try {
      const payload = await scrapeCharactersMutation.trigger({
        source_url: scrapeUrl.trim(),
        acknowledge_source_risk: true,
      });
      setScrapedCandidates(payload.candidates);
      setCharacterExtractionWarnings(payload.warnings ?? []);
      toast.success(`Scraped ${payload.candidate_count} character candidates.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Character scrape failed.');
    }
  }

  async function handleMergeCharacters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }

    const normalizedMergeUrl = mergeScrapeUrl.trim();
    if (normalizedMergeUrl && !mergeScrapeAcknowledged) {
      toast.error('Acknowledge the scrape warning to include web-scrape data.');
      return;
    }

    try {
      const payload = {
        include_auto: true,
        source_url: normalizedMergeUrl || undefined,
        acknowledge_source_risk: normalizedMergeUrl ? mergeScrapeAcknowledged : false,
      };
      const merged = await mergeCharactersMutation.trigger(payload);
      setMergeCandidates(merged.candidates);
      setProposedCandidates(merged.proposed_characters);
      setMergeSuggestions(merged.canonical_merge_suggestions);
      setCharacterExtractionWarnings(merged.warnings ?? []);
      setMergeUndoHistory([]);
      toast.success(`Merged ${merged.candidate_count} candidate records.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Character merge failed.');
    }
  }

  function updateRow(rowId: string, field: keyof ManualCharacterRow, value: string) {
    setManualRows((prev) => prev.map((row) => (row.id === rowId ? { ...row, [field]: value } : row)));
  }

  function addRow() {
    setManualRows((prev) => [...prev, createRow()]);
  }

  function removeRow(rowId: string) {
    setManualRows((prev) => prev.filter((row) => row.id !== rowId));
  }

  function handleApproveProposedCandidate(index: number) {
    const candidate = proposedCandidates[index];
    if (!candidate || !candidate.name.trim()) {
      return;
    }

    setManualRows((prev) => {
      const existingIndex = prev.findIndex(
        (row) => row.name.trim().toLowerCase() === candidate.name.trim().toLowerCase(),
      );
      if (existingIndex >= 0) {
        const nextRows = [...prev];
        nextRows[existingIndex] = {
          ...nextRows[existingIndex],
          name: candidate.name,
          verbalized: candidate.verbalized_form,
          gender: candidate.gender,
          aliases: candidate.aliases.join(', '),
        };
        return nextRows;
      }

      const nextRows = [
        ...prev,
        {
          id: crypto.randomUUID(),
          name: candidate.name,
          verbalized: candidate.verbalized_form,
          gender: candidate.gender,
          aliases: candidate.aliases.join(', '),
        },
      ];
      return nextRows;
    });

    setProposedCandidates((prev) => prev.filter((_, candidateIndex) => candidateIndex !== index));
  }

  function handleRejectProposedCandidate(index: number) {
    setProposedCandidates((prev) => prev.filter((_, candidateIndex) => candidateIndex !== index));
  }

  function handleApplyCanonicalMergeSuggestion(index: number) {
    const suggestion = mergeSuggestions[index];
    if (!suggestion || !suggestion.alias_name || !suggestion.canonical_name) {
      return;
    }

    const nextRows = mergeManualRows(manualRows, suggestion.canonical_name, suggestion.alias_name);
    if (nextRows === null) {
      toast.error(
        `Could not apply merge for ${suggestion.alias_name} → ${suggestion.canonical_name}; ensure both characters are present.`,
      );
      return;
    }

    setMergeUndoHistory((prev) => [
      ...prev,
      {
        previousManualRows: manualRows,
        previousMergeSuggestions: mergeSuggestions,
        canonicalName: suggestion.canonical_name,
        aliasName: suggestion.alias_name,
      },
    ]);
    setManualRows(nextRows);
    setMergeSuggestions((prev) => prev.filter((_, suggestionIndex) => suggestionIndex !== index));
    toast.success(`Merged "${suggestion.alias_name}" into "${suggestion.canonical_name}".`);
  }

  function handleUndoLastMergeSuggestion() {
    const previous = mergeUndoHistory[mergeUndoHistory.length - 1];
    if (!previous) {
      return;
    }

    setManualRows(previous.previousManualRows);
    setMergeSuggestions(previous.previousMergeSuggestions);
    setMergeUndoHistory((prev) => prev.slice(0, -1));
  }

  async function handleFinalizeCharacterMap() {
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }

    try {
      await finalizeCharactersMutation.trigger();
      await characterMapQuery.mutate();
      toast.success('Character map finalized.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to finalize character map.');
    }
  }

  async function handleInferCharacterGenders() {
    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }

    try {
      const inferredMap = await inferCharacterGendersMutation.trigger();
      setManualRows(toManualRows(inferredMap));
      setLastSavedCount(inferredMap.characters.length);
      await characterGenderComparisonQuery.mutate();
      toast.success('Character genders inferred.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Unable to infer character genders.');
    }
  }

  async function handlePronunciationPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (projectId === null) {
      toast.error('Project is missing.');
      return;
    }
    if (!pronunciationPreviewText.trim()) {
      toast.error('Provide sample text for preview.');
      return;
    }
    if (
      !includeGlobalPronunciationScope &&
      !includeCharacterPronunciationScope &&
      !includePlacePronunciationScope &&
      !includeArtifactPronunciationScope &&
      !includeInventedPronunciationScope
    ) {
      toast.error('Enable at least one pronunciation scope before previewing.');
      return;
    }
    if (includeCharacterPronunciationScope && !pronunciationPreviewCharacterName.trim()) {
      toast.error('Choose a character name for character-scoped preview.');
      return;
    }

    const requestPayload: PronunciationDictionaryPreviewRequestDto = {
      text: pronunciationPreviewText.trim(),
      include_global_scope: includeGlobalPronunciationScope,
      include_character_scope: includeCharacterPronunciationScope,
      include_place_scope: includePlacePronunciationScope,
      include_artifact_scope: includeArtifactPronunciationScope,
      include_invented_scope: includeInventedPronunciationScope,
      match_whole_words: pronunciationMatchWholeWords,
      case_sensitive: pronunciationCaseSensitive,
      alias_aware: pronunciationAliasAware,
      ...(pronunciationPreviewCharacterName.trim() ? { character_name: pronunciationPreviewCharacterName.trim() } : {}),
    };

    try {
      const previewResult = await pronunciationPreviewMutation.trigger(requestPayload);
      setPronunciationPreviewResult(previewResult);
      toast.success('Pronunciation preview generated.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Pronunciation preview failed.');
    }
  }

  return (
    <WorkflowPageShell
      step="Step 03"
      title="Character Map"
      description="Manage character data through import, manual editing, and scrape-assisted discovery. This page is dedicated to character-map operations only."
      showOutputDisclaimer
      action={
        projectId !== null ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={inferCharacterGendersMutation.isMutating || projectId === null}
              onClick={handleInferCharacterGenders}
              type="button"
            >
              {inferCharacterGendersMutation.isMutating ? 'Inferring genders...' : 'Infer Character Genders'}
            </Button>
            <Button
              size="sm"
              variant={isCharacterMapFinalized ? 'outline' : 'default'}
              disabled={finalizeCharactersMutation.isMutating || projectId === null || isCharacterMapFinalized}
              onClick={handleFinalizeCharacterMap}
              type="button"
            >
              {finalizeCharactersMutation.isMutating
                ? 'Finalizing...'
                : isCharacterMapFinalized
                  ? 'Character Map Finalized'
                  : 'Finalize Character Map'}
            </Button>
            <Button onClick={() => navigate(projectRoute(projectId, 'pipeline-setup'))}>Continue to Pipeline Setup</Button>
          </div>
        ) : (
          <Badge variant="outline">Project required</Badge>
        )
      }
    >
      <div className="grid gap-4 lg:grid-cols-[0.95fr_1.55fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileUp className="size-4 text-primary" />
              Import & Scrape
            </CardTitle>
            <CardDescription>Import a character map first. Scrape stays optional.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <form className="grid gap-3" onSubmit={handleImport}>
              <div className="grid gap-2">
                <Label htmlFor="character-file">CSV / JSON file</Label>
                <Input
                  id="character-file"
                  accept=".csv,.json"
                  data-testid="character-file-input"
                  onChange={(event) => setCharacterFile(event.target.files?.[0] ?? null)}
                  type="file"
                />
              </div>
              <Button data-testid="character-import-button" disabled={importCharactersMutation.isMutating || projectId === null} type="submit">
                {importCharactersMutation.isMutating ? 'Importing...' : 'Import Character Map'}
              </Button>
              <p className="text-sm text-muted-foreground" data-testid="character-import-state">
                {importedCount !== null ? `Imported rows: ${importedCount}` : 'No import completed yet.'}
              </p>
            </form>

            {aliasCollisionWarnings.length === 0 ? null : (
              <div
                className="space-y-2 rounded-md border border-amber-300/50 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100"
                data-testid="character-alias-collision-warnings"
              >
                <p className="font-medium">Character warnings</p>
                <ul className="space-y-1 text-xs">
                  {aliasCollisionWarnings.map((warning) => (
                    <li className="space-y-0.5" key={`${warning.alias}-${warning.source}`}>
                      <p>
                        {warning.alias} → {warning.canonical_names.join(', ')}
                      </p>
                      <p className="text-[11px] opacity-90">{warning.message}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {lowConfidenceWarnings.length === 0 ? null : (
              <div
                className="space-y-2 rounded-md border border-amber-300/50 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100"
                data-testid="character-low-confidence-warnings"
              >
                <p className="font-medium">Low-confidence extracted characters</p>
                <ul className="space-y-1 text-xs">
                  {lowConfidenceWarnings.map((warning) => {
                    const warningConfidence = warning.confidence === undefined ? 'low' : `${Math.round(warning.confidence * 100)}%`;
                    const warningThreshold =
                      warning.threshold === undefined ? '' : ` (threshold: ${Math.round(warning.threshold * 100)}%)`;
                    const warningName = warning.candidate_name || warning.alias;

                    return (
                      <li className="space-y-0.5" key={`${warning.alias}-${warning.source}-${warningConfidence}-${warningThreshold}`}>
                        <p>
                          {warningName} · {warningConfidence}{warningThreshold}
                        </p>
                        <p className="text-[11px] opacity-90">{warning.message}</p>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            <div className="space-y-2 text-sm text-muted-foreground">
              <form className="grid gap-2" onSubmit={handleAutoExtract}>
                <p className="font-medium text-foreground">Auto extraction</p>
                <Button variant="outline" disabled={autoExtractCharactersMutation.isMutating || projectId === null} type="submit">
                  {autoExtractCharactersMutation.isMutating ? 'Extracting...' : 'Extract candidate names from text'}
                </Button>
                <p data-testid="character-auto-extract-state" className="text-xs">
                  {autoExtractedCandidates.length === 0
                    ? 'No candidates extracted yet.'
                    : `Latest candidates: ${autoExtractedCandidates.length}`}
                </p>
              </form>
              {autoExtractedCandidates.length === 0 ? null : (
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {autoExtractedCandidates.map((candidate) => (
                    <li className="space-y-1" key={candidate.name}>
                      <div className="flex items-center justify-between gap-2">
                        <span>{candidate.name}</span>
                        <span>{Math.round(candidate.confidence * 100)}% confidence</span>
                      </div>
                      {candidate.source_trace.length === 0 ? null : (
                        <ul className="space-y-0.5 pl-2 text-[11px]">
                          {candidate.source_trace.map((trace) => (
                            <li key={`${candidate.name}-${trace.chapter_index}-${trace.span_start}-${trace.span_end}`}>
                              <span className="font-medium text-foreground">Ch {trace.chapter_index}</span> ·{' '}
                              {trace.kind.replaceAll('_', ' ')} · weight {Math.round(trace.weight * 100)}% ·{' '}
                              <span className="italic">{trace.excerpt}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p className="flex items-center gap-2 font-medium text-foreground">
                <WandSparkles className="size-4 text-primary" />
                Scrape candidates
              </p>
              {appEnv.featureScrapeEnabled ? (
                <form className="grid gap-2" onSubmit={handleScrapeCharacters}>
                  <p
                    className="rounded-md border border-amber-300/60 bg-amber-50 px-3 py-2 text-xs text-amber-950 dark:border-amber-500/35 dark:bg-amber-500/10 dark:text-amber-100"
                    data-testid="character-scrape-warning"
                  >
                    <span className="font-semibold">Legal warning:</span> {SCRAPE_LEGAL_WARNING_TEXT}
                  </p>
                  <Input
                    id="character-scrape-url"
                    aria-label="Character scrape source URL"
                    placeholder="https://example.com/author-page"
                    value={scrapeUrl}
                    onChange={(event) => setScrapeUrl(event.target.value)}
                  />
                  <label className="flex items-start gap-2 text-xs text-muted-foreground">
                    <Checkbox
                      aria-label="Acknowledge scrape warning"
                      checked={scrapeWarningAcknowledged}
                      onCheckedChange={(checked) => setScrapeWarningAcknowledged(checked === true)}
                    />
                    <span>
                      I acknowledge this is a web-scrape source and accept the legal and accuracy risks above.
                    </span>
                  </label>
                  <Button
                    variant="outline"
                    disabled={
                      scrapeCharactersMutation.isMutating || !scrapeWarningAcknowledged || projectId === null || !scrapeUrl.trim()
                    }
                    type="submit"
                  >
                    {scrapeCharactersMutation.isMutating ? 'Scraping...' : 'Scrape candidates'}
                  </Button>
                  <p data-testid="character-scrape-state" className="text-xs">
                    {scrapedCandidates.length === 0
                      ? 'No scrape results yet.'
                      : `Scrape candidates: ${scrapedCandidates.length}`}
                  </p>
                </form>
              ) : (
                <div className="space-y-2">
                  <p className="inline-flex items-center gap-1 text-xs font-medium uppercase tracking-[0.08em]">
                    <AlertCircle className="size-3.5 text-muted-foreground" />
                    Disabled by environment flag
                  </p>
                  <p>Enable with `VITE_FEATURE_SCRAPE_ENABLED=true` to allow web-scrape candidate ingestion in this environment.</p>
                </div>
              )}
              {scrapedCandidates.length === 0 ? null : (
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {scrapedCandidates.map((candidate) => (
                    <li className="space-y-1" key={`scrape-${candidate.name}`}>
                      <div className="flex items-center justify-between gap-2">
                        <span>{candidate.name}</span>
                        <span>{Math.round(candidate.confidence * 100)}% confidence</span>
                      </div>
                      {candidate.source_trace.length === 0 ? null : (
                        <ul className="space-y-0.5 pl-2 text-[11px]">
                          {candidate.source_trace.map((trace) => (
                            <li key={`scrape-${candidate.name}-${trace.chapter_index}-${trace.span_start}-${trace.span_end}`}>
                              <span className="font-medium text-foreground">Ch {trace.chapter_index}</span> ·{' '}
                              {trace.kind.replaceAll('_', ' ')} · weight {Math.round(trace.weight * 100)}% ·{' '}
                              <span className="italic">{trace.excerpt}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Merged candidates</p>
              <form className="grid gap-2" onSubmit={handleMergeCharacters}>
                <p className="text-xs">Combine user-uploaded and auto-discovered candidates; add scrape URL to include external candidates.</p>
                <p
                  className="rounded-md border border-amber-300/60 bg-amber-50 px-3 py-2 text-xs text-amber-950 dark:border-amber-500/35 dark:bg-amber-500/10 dark:text-amber-100"
                  data-testid="character-merge-scrape-warning"
                >
                  <span className="font-semibold">Legal warning:</span> {SCRAPE_LEGAL_WARNING_TEXT}
                </p>
                <Input
                  id="character-merge-scrape-url"
                  aria-label="Optional merge scrape source URL"
                  placeholder="Optional: https://example.com/author-page"
                  value={mergeScrapeUrl}
                  onChange={(event) => setMergeScrapeUrl(event.target.value)}
                />
                <label className="flex items-start gap-2 text-xs text-muted-foreground">
                  <Checkbox
                    aria-label="Acknowledge merge scrape warning"
                    checked={mergeScrapeAcknowledged}
                    onCheckedChange={(checked) => setMergeScrapeAcknowledged(checked === true)}
                    disabled={!mergeScrapeUrl.trim()}
                  />
                  <span>
                    Include scraped candidates only after confirming this warning and accepting source limitations.
                  </span>
                </label>
                <Button
                  variant="outline"
                  disabled={
                    mergeCharactersMutation.isMutating || projectId === null || (mergeScrapeUrl.trim() !== '' && !mergeScrapeAcknowledged)
                  }
                  type="submit"
                >
                  {mergeCharactersMutation.isMutating ? 'Merging...' : 'Merge user + auto + scraped candidates'}
                </Button>
                <p data-testid="character-merged-state" className="text-xs">
                  {mergeCandidates.length === 0 ? 'No merged candidates yet.' : `Merged candidates: ${mergeCandidates.length}`}
                </p>
              </form>
              {mergeCandidates.length === 0 ? null : (
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {mergeCandidates.map((candidate) => (
                    <li className="space-y-1" key={`merged-${candidate.name}-${candidate.source}`}>
                      <div className="flex items-center justify-between gap-2">
                        <span>{candidate.name}</span>
                        <span>{Math.round(candidate.confidence * 100)}% · {candidate.source}</span>
                      </div>
                      {candidate.source_trace.length === 0 ? null : (
                        <ul className="space-y-0.5 pl-2 text-[11px]">
                          {candidate.source_trace.map((trace) => (
                            <li key={`merged-${candidate.name}-${trace.chapter_index}-${trace.span_start}-${trace.span_end}`}>
                              <span className="font-medium text-foreground">Ch {trace.chapter_index}</span> ·{' '}
                              {trace.kind.replaceAll('_', ' ')} · weight {Math.round(trace.weight * 100)}% ·{' '}
                              <span className="italic">{trace.excerpt}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Canonical-name merge suggestions</p>
              <p className="text-xs">Candidates that look similar to existing canonicals and may be merged.</p>
              <div className="flex items-center justify-between gap-2">
                <p data-testid="character-merge-suggestions-state" className="text-xs">
                  {mergeSuggestions.length === 0 ? 'No suggestions yet.' : `${mergeSuggestions.length} suggestion(s).`}
                </p>
                {mergeUndoHistory.length === 0 ? null : (
                  <Button
                    data-testid="character-merge-suggestions-undo"
                    size="sm"
                    variant="outline"
                    onClick={handleUndoLastMergeSuggestion}
                    type="button"
                  >
                    Undo last merge
                  </Button>
                )}
              </div>
              {mergeSuggestions.length === 0 ? null : (
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {mergeSuggestions.map((suggestion, index) => (
                    <li
                      key={`merge-suggestion-${suggestion.alias_name}-${suggestion.canonical_name}`}
                      className="space-y-0.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span>
                          {suggestion.alias_name} → {suggestion.canonical_name}
                        </span>
                        <span>{Math.round(suggestion.score * 100)}% similar</span>
                      </div>
                      <Button
                        size="sm"
                        onClick={() => handleApplyCanonicalMergeSuggestion(index)}
                        type="button"
                      >
                        Apply
                      </Button>
                      <p className="text-[11px] text-muted-foreground/90">Reason: {suggestion.reason}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Proposed characters review screen</p>
              <p className="text-xs">Review proposed candidates before adding them to the character map.</p>
              <p data-testid="character-proposed-state" className="text-xs">
                {proposedCandidates.length === 0
                  ? 'No proposed characters to review.'
                  : `${proposedCandidates.length} proposed character(s) ready for review.`}
              </p>
              {proposedCandidates.length === 0 ? null : (
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {proposedCandidates.map((candidate, index) => (
                    <li
                      className="space-y-1"
                      key={`proposed-${candidate.name}-${candidate.source}-${index}`}
                      data-testid={`proposed-character-${candidate.name.toLowerCase().replace(/\s+/g, '-')}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span>{candidate.name}</span>
                        <span>{Math.round(candidate.confidence * 100)}% · {candidate.source}</span>
                      </div>
                      {candidate.source_trace.length === 0 ? null : (
                        <ul className="space-y-0.5 pl-2 text-[11px]">
                          {candidate.source_trace.map((trace) => (
                            <li key={`proposed-${candidate.name}-${trace.chapter_index}-${trace.span_start}-${trace.span_end}`}>
                              <span className="font-medium text-foreground">Ch {trace.chapter_index}</span> ·{' '}
                              {trace.kind.replaceAll('_', ' ')} · weight {Math.round(trace.weight * 100)}% ·{' '}
                              <span className="italic">{trace.excerpt}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleApproveProposedCandidate(index)}
                          type="button"
                        >
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleRejectProposedCandidate(index)}
                          type="button"
                        >
                          Reject
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="text-sm text-muted-foreground" data-testid="character-list-state">
              {characterMapQuery.isLoading
                ? 'Loading saved character map.'
                : `${characterMapQuery.data?.characters.length ?? 0} row(s) loaded.`}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserCog className="size-4 text-primary" />
              Manual Editor
            </CardTitle>
            <CardDescription>Add, adjust, and remove rows and persist them immediately to this project.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {genderContradictionRows.length === 0 ? null : (
              <p
                data-testid="character-gender-contradiction-state"
                className="rounded border border-amber-300/70 bg-amber-50 px-3 py-2 text-xs text-amber-900"
              >
                {genderContradictionRows.length} manual gender override contradiction(s) detected.
              </p>
            )}
            <div className="grid max-h-[28rem] gap-1 overflow-auto pr-1">
              {manualRows.map((row) => (
                <div
                  key={row.id}
                  className="grid gap-2 px-1 py-1.5 [&:not(:last-child)]:border-b [&:not(:last-child)]:border-panel-border/60"
                >
                  {(() => {
                    const inferredGender = genderComparisonRows[row.name.trim().toLowerCase()] ?? row.inferredGender;

                    return (
                      <>
                        <div className="space-y-1">
                          <Input
                            placeholder="Character name"
                            value={row.name}
                            onChange={(event) => updateRow(row.id, 'name', event.target.value)}
                            className={manualRowErrors[row.id]?.name ? 'border-destructive' : undefined}
                          />
                          {manualRowErrors[row.id]?.name ? (
                            <p className="text-xs text-destructive">{manualRowErrors[row.id]!.name}</p>
                          ) : null}
                        </div>
                        <div className="grid gap-2 lg:grid-cols-[1fr_1fr_1.3fr_160px_auto]">
                          <Input
                            placeholder="Verbalized form"
                            value={row.verbalized}
                            onChange={(event) => updateRow(row.id, 'verbalized', event.target.value)}
                            className={manualRowErrors[row.id]?.verbalized ? 'border-destructive' : undefined}
                          />
                          {manualRowErrors[row.id]?.verbalized ? (
                            <p className="text-xs text-destructive">{manualRowErrors[row.id]!.verbalized}</p>
                          ) : null}
                          <Input
                            placeholder="Aliases (comma-separated)"
                            value={row.aliases}
                            onChange={(event) => updateRow(row.id, 'aliases', event.target.value)}
                          />
                          <NativeSelect value={row.gender} onChange={(event) => updateRow(row.id, 'gender', event.target.value)}>
                            <option value="male">male</option>
                            <option value="female">female</option>
                            <option value="neutral">neutral</option>
                            <option value="unknown">unknown</option>
                            <option value="custom">custom</option>
                          </NativeSelect>
                          {isGenderContradiction(row.gender, inferredGender) ? (
                            <p className="col-span-full text-xs text-amber-900">
                              <span className="font-medium">Contradiction:</span> manual={normalizeGender(row.gender)},
                              inferred={normalizeGender(inferredGender)}.
                            </p>
                          ) : null}
                          <Button variant="outline" onClick={() => removeRow(row.id)} type="button">
                            Remove
                          </Button>
                        </div>
                      </>
                    );
                  })()}
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between gap-3 pt-2">
              <Button variant="outline" onClick={addRow} type="button">
                <Plus className="size-4" />
                Add Row
              </Button>
              <p className="text-sm text-muted-foreground">
                Ready rows: {manualPreviewCount}
                {lastSavedCount === null ? null : ` · Last saved: ${lastSavedCount}`}
              </p>
            </div>
            <form className="grid" onSubmit={handleSaveManualCharacters}>
              <Button
                data-testid="character-map-save-button"
                disabled={saveCharactersMutation.isMutating || projectId === null || hasManualRowErrors}
                type="submit"
              >
                {saveCharactersMutation.isMutating ? 'Saving...' : 'Save Character Map'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="size-4 text-primary" />
              Pronunciation Check Preview
            </CardTitle>
            <CardDescription>Check dictionary substitutions before running the pipeline.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form className="grid gap-3" onSubmit={handlePronunciationPreview}>
              <div className="grid gap-2">
                <Label htmlFor="pronunciation-preview-text">Sample text</Label>
                <Textarea
                  id="pronunciation-preview-text"
                  rows={6}
                  value={pronunciationPreviewText}
                  onChange={(event) => setPronunciationPreviewText(event.target.value)}
                  placeholder="Paste a paragraph or dialogue line here..."
                  data-testid="pronunciation-preview-text"
                />
              </div>
              <div className="grid gap-2">
                <p className="text-sm font-medium">Scope</p>
                <div className="flex flex-wrap items-center gap-3">
                  <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                    <Checkbox
                      checked={includeGlobalPronunciationScope}
                      onCheckedChange={(checked) => setIncludeGlobalPronunciationScope(checked === true)}
                    />
                    <span>Global pronunciation dictionary</span>
                  </label>
                  <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                    <Checkbox
                      checked={includeCharacterPronunciationScope}
                      onCheckedChange={(checked) => setIncludeCharacterPronunciationScope(checked === true)}
                    />
                    <span>Character-specific dictionary</span>
                  </label>
                  <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                    <Checkbox
                      checked={includePlacePronunciationScope}
                      onCheckedChange={(checked) => setIncludePlacePronunciationScope(checked === true)}
                    />
                    <span>Place-name pronunciation dictionary</span>
                  </label>
                  <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                    <Checkbox
                      checked={includeArtifactPronunciationScope}
                      onCheckedChange={(checked) => setIncludeArtifactPronunciationScope(checked === true)}
                    />
                    <span>Artifact terminology dictionary</span>
                  </label>
                  <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                    <Checkbox
                      checked={includeInventedPronunciationScope}
                      onCheckedChange={(checked) => setIncludeInventedPronunciationScope(checked === true)}
                    />
                    <span>Invented word dictionary</span>
                  </label>
                </div>
              </div>
              <div className="grid gap-2">
                <p className="text-sm font-medium">Matching mode</p>
                <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <Checkbox
                    checked={pronunciationMatchWholeWords}
                    onCheckedChange={(checked) => setPronunciationMatchWholeWords(checked === true)}
                  />
                  <span>Match whole words only</span>
                </label>
                <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <Checkbox
                    checked={pronunciationCaseSensitive}
                    onCheckedChange={(checked) => setPronunciationCaseSensitive(checked === true)}
                  />
                  <span>Case-sensitive matching</span>
                </label>
                <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <Checkbox
                    checked={pronunciationAliasAware}
                    onCheckedChange={(checked) => setPronunciationAliasAware(checked === true)}
                  />
                  <span>Alias-aware substitution</span>
                </label>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="pronunciation-preview-character">Character scope target</Label>
                <NativeSelect
                  id="pronunciation-preview-character"
                  value={pronunciationPreviewCharacterName}
                  onChange={(event) => setPronunciationPreviewCharacterName(event.target.value)}
                  disabled={!includeCharacterPronunciationScope}
                >
                  <option value="">Select character (optional)</option>
                  {characterNameOptions.map((characterName) => (
                    <option key={characterName} value={characterName}>
                      {characterName}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <Button
                data-testid="pronunciation-preview-button"
                disabled={
                  pronunciationPreviewMutation.isMutating ||
                  !pronunciationPreviewText.trim() ||
                  projectId === null ||
                  (!includeGlobalPronunciationScope &&
                    !includeCharacterPronunciationScope &&
                    !includePlacePronunciationScope &&
                    !includeArtifactPronunciationScope &&
                    !includeInventedPronunciationScope) ||
                  (includeCharacterPronunciationScope && !pronunciationPreviewCharacterName.trim())
                }
                type="submit"
              >
                {pronunciationPreviewMutation.isMutating ? 'Previewing...' : 'Run Pronunciation Preview'}
              </Button>
            </form>
            <div className="space-y-2">
              {pronunciationPreviewResult === null ? (
                <p className="text-sm text-muted-foreground">Run a sample preview to inspect substitutions.</p>
              ) : (
                <>
                  <div className="text-sm text-muted-foreground">
                    Included scopes:{' '}
                    {pronunciationPreviewResult.included_scopes.length === 0
                      ? 'none'
                      : pronunciationPreviewResult.included_scopes.join(', ')}
                  </div>
                  {(pronunciationPreviewResult.warnings ?? []).length > 0 ? (
                    <div className="rounded-md border border-amber-300/70 bg-amber-50 p-3 text-sm text-amber-900">
                      <p className="mb-2 inline-flex items-center gap-2 font-medium">
                        <AlertCircle className="size-4" />
                        Ambiguous replacements detected
                      </p>
                      <ul className="space-y-2" data-testid="pronunciation-preview-warnings">
                        {(pronunciationPreviewResult.warnings ?? []).map((warning) => (
                          <li
                            className="space-y-1"
                            key={`${warning.type}-${warning.term}-${warning.scopes.join(',')}-${warning.competing_verbalized_forms.join(',')}`}
                          >
                            <p>{warning.message}</p>
                            <p className="text-xs">
                              Competing verbalized forms: {warning.competing_verbalized_forms.join(', ')}
                            </p>
                            <p className="text-xs">Scopes: {warning.scopes.join(', ')}</p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  <div className="grid gap-2">
                    <div className="grid gap-1">
                      <Label htmlFor="pronunciation-preview-before">Before</Label>
                      <Textarea
                        id="pronunciation-preview-before"
                        readOnly
                        value={pronunciationPreviewResult.before}
                        rows={4}
                        data-testid="pronunciation-preview-before"
                      />
                    </div>
                    <div className="grid gap-1">
                      <Label htmlFor="pronunciation-preview-after">After</Label>
                      <Textarea
                        id="pronunciation-preview-after"
                        readOnly
                        value={pronunciationPreviewResult.after}
                        rows={4}
                        data-testid="pronunciation-preview-after"
                      />
                    </div>
                  </div>
                  <div className="space-y-1 text-xs text-muted-foreground">
                    <p className="text-sm text-foreground">Replacement summary</p>
                    {pronunciationPreviewResult.replacements.length === 0 ? (
                      <p>No replacements were applied.</p>
                    ) : (
                      <ul className="space-y-1" data-testid="pronunciation-preview-replacements">
                        {pronunciationPreviewResult.replacements.map((replacement) => (
                          <li
                            className="flex flex-wrap items-center justify-between gap-2"
                            key={`${pronunciationPreviewResult.project_id}-${replacement.term}-${replacement.scope}-${replacement.verbalized_form}`}
                          >
                            <span>
                              {replacement.term} → {replacement.verbalized_form}
                            </span>
                            <span>
                              {replacement.count}x · {replacement.scope}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </WorkflowPageShell>
  );
}
