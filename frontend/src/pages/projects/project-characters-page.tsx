import { type FormEvent, useEffect, useMemo, useState } from 'react';

import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { AlertCircle, FileUp, Plus, UserCog, WandSparkles } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { appEnv } from '@/app/config/env';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import type { CharacterExtractionDto, CharacterMapDto } from '@/app/schemas/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import {
  useAutoExtractCharactersMutation,
  useCharacterMapQuery,
  useScrapeCharactersMutation,
  useMergeCharactersMutation,
  useImportCharactersMutation,
  useSaveCharacterMapMutation,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';
import { Checkbox } from '@/components/ui/checkbox';

type ManualCharacterRow = {
  id: string;
  name: string;
  verbalized: string;
  gender: string;
};

function createRow(): ManualCharacterRow {
  return {
    id: crypto.randomUUID(),
    name: '',
    verbalized: '',
    gender: 'unknown',
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
  }));
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
  const [mergeScrapeUrl, setMergeScrapeUrl] = useState<string>('');
  const [mergeScrapeAcknowledged, setMergeScrapeAcknowledged] = useState<boolean>(false);

  const [manualRows, setManualRows] = useState<ManualCharacterRow[]>([createRow()]);
  const manualPreviewCount = useMemo(
    () => manualRows.filter((row) => row.name.trim() && row.verbalized.trim()).length,
    [manualRows],
  );

  const characterMapQuery = useCharacterMapQuery(projectId);
  const saveCharactersMutation = useSaveCharacterMapMutation(projectId);
  const autoExtractCharactersMutation = useAutoExtractCharactersMutation(projectId);
  const scrapeCharactersMutation = useScrapeCharactersMutation(projectId);
  const mergeCharactersMutation = useMergeCharactersMutation(projectId);

  useEffect(() => {
    if (characterMapQuery.data === undefined) {
      return;
    }
    setManualRows(toManualRows(characterMapQuery.data));
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

    const payloadCharacters = manualRows
      .map((row) => ({
        name: row.name.trim(),
        verbalized_form: row.verbalized.trim(),
        gender: row.gender.trim().toLowerCase(),
      }))
      .filter((row) => row.name && row.verbalized_form)
      .map((row) => ({
        ...row,
        aliases: [],
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
        },
      ];
      return nextRows;
    });

    setProposedCandidates((prev) => prev.filter((_, candidateIndex) => candidateIndex !== index));
  }

  function handleRejectProposedCandidate(index: number) {
    setProposedCandidates((prev) => prev.filter((_, candidateIndex) => candidateIndex !== index));
  }

  return (
    <WorkflowPageShell
      step="Step 03"
      title="Character Map"
      description="Manage character data through import, manual editing, and scrape-assisted discovery. This page is dedicated to character-map operations only."
      action={
        projectId !== null ? (
          <Button onClick={() => navigate(projectRoute(projectId, 'pipeline-setup'))}>Continue to Pipeline Setup</Button>
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
                  <Input
                    id="character-scrape-url"
                    aria-label="Character scrape source URL"
                    placeholder="https://example.com/author-page"
                    value={scrapeUrl}
                    onChange={(event) => setScrapeUrl(event.target.value)}
                  />
                  <label className="flex items-start gap-2 text-xs text-muted-foreground">
                    <Checkbox
                      checked={scrapeWarningAcknowledged}
                      onCheckedChange={(checked) => setScrapeWarningAcknowledged(checked === true)}
                    />
                    <span>
                      I understand this source is external and may have accuracy or legal constraints; scraped candidates may be inaccurate and
                      should be reviewed.
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
                <Input
                  id="character-merge-scrape-url"
                  aria-label="Optional merge scrape source URL"
                  placeholder="Optional: https://example.com/author-page"
                  value={mergeScrapeUrl}
                  onChange={(event) => setMergeScrapeUrl(event.target.value)}
                />
                <label className="flex items-start gap-2 text-xs text-muted-foreground">
                  <Checkbox
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
              <p data-testid="character-merge-suggestions-state" className="text-xs">
                {mergeSuggestions.length === 0 ? 'No suggestions yet.' : `${mergeSuggestions.length} suggestion(s).`}
              </p>
              {mergeSuggestions.length === 0 ? null : (
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {mergeSuggestions.map((suggestion) => (
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
            <div className="grid max-h-[28rem] gap-1 overflow-auto pr-1">
              {manualRows.map((row) => (
                <div key={row.id} className="grid gap-2 px-1 py-1.5 [&:not(:last-child)]:border-b [&:not(:last-child)]:border-panel-border/60">
                  <div className="grid gap-2 lg:grid-cols-[1fr_1fr_160px_auto]">
                    <Input
                      placeholder="Character name"
                      value={row.name}
                      onChange={(event) => updateRow(row.id, 'name', event.target.value)}
                    />
                    <Input
                      placeholder="Verbalized form"
                      value={row.verbalized}
                      onChange={(event) => updateRow(row.id, 'verbalized', event.target.value)}
                    />
                    <NativeSelect value={row.gender} onChange={(event) => updateRow(row.id, 'gender', event.target.value)}>
                      <option value="male">male</option>
                      <option value="female">female</option>
                      <option value="neutral">neutral</option>
                      <option value="unknown">unknown</option>
                      <option value="custom">custom</option>
                    </NativeSelect>
                    <Button variant="outline" onClick={() => removeRow(row.id)} type="button">
                      Remove
                    </Button>
                  </div>
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
                disabled={saveCharactersMutation.isMutating || projectId === null}
                type="submit"
              >
                {saveCharactersMutation.isMutating ? 'Saving...' : 'Save Character Map'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </WorkflowPageShell>
  );
}
