import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  WandSparkles,
  FileUp,
  CheckCheck,
  Search,
  Globe,
  Merge,
  UserCheck,
  AlertTriangle,
} from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  useAutoExtractCharactersMutation,
  useCharacterMapQuery,
  useFinalizeCharacterMapMutation,
  useImportCharactersMutation,
  useScrapeCharactersMutation,
  useMergeCharactersMutation,
  useInferCharacterGendersMutation,
  useLookupCharacterAliasMutation,
  useCharacterAliasCollisionsQuery,
  useCharacterGenderComparisonQuery,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { cn } from '@/lib/utils';

const GENDER_BADGE: Record<string, string> = {
  male: 'bg-blue-400/10 text-blue-400',
  female: 'bg-pink-400/10 text-pink-400',
  neutral: 'bg-purple-400/10 text-purple-400',
  unknown: 'bg-white/5 text-muted-foreground',
  custom: 'bg-amber-400/10 text-amber-400',
};

type ActiveTool = 'none' | 'scrape' | 'alias' | 'genders';

export function ProjectCharactersPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;

  const [search, setSearch] = useState('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [scrapeUrl, setScrapeUrl] = useState('');
  const [aliasQuery, setAliasQuery] = useState('');
  const [aliasResult, setAliasResult] = useState<{ canonical_name: string | null; match_source: string } | null>(null);
  const [activeTool, setActiveTool] = useState<ActiveTool>('none');
  const [lastExtractionResult, setLastExtractionResult] = useState<{ canonical_merge_suggestions: Array<{ canonical_name: string; alias_name: string; score: number; reason: string }> } | null>(null);

  const characterMapQuery = useCharacterMapQuery(projectId);
  const aliasCollisionsQuery = useCharacterAliasCollisionsQuery(projectId);
  const genderComparisonQuery = useCharacterGenderComparisonQuery(projectId);
  const extractMutation = useAutoExtractCharactersMutation(projectId);
  const finalizeMutation = useFinalizeCharacterMapMutation(projectId);
  const importMutation = useImportCharactersMutation(projectId);
  const scrapeMutation = useScrapeCharactersMutation(projectId);
  const mergeMutation = useMergeCharactersMutation(projectId);
  const inferGendersMutation = useInferCharacterGendersMutation(projectId);
  const lookupAliasMutation = useLookupCharacterAliasMutation(projectId);

  const characters = characterMapQuery.data?.characters ?? [];
  const mergeWarnings = lastExtractionResult?.canonical_merge_suggestions ?? [];
  const aliasCollisions = aliasCollisionsQuery.data?.collisions ?? [];

  const filtered = search.trim()
    ? characters.filter((c) =>
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.aliases?.some((a) => a.toLowerCase().includes(search.toLowerCase()))
      )
    : characters;

  const isBusy =
    extractMutation.isMutating ||
    finalizeMutation.isMutating ||
    importMutation.isMutating ||
    scrapeMutation.isMutating ||
    mergeMutation.isMutating ||
    inferGendersMutation.isMutating;

  function toggleTool(tool: ActiveTool) {
    setActiveTool((prev) => (prev === tool ? 'none' : tool));
  }

  async function handleExtract() {
    try {
      const result = await extractMutation.trigger();
      setLastExtractionResult(result ?? null);
      await characterMapQuery.mutate();
      toast.success('Character extraction complete.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Extraction failed');
    }
  }

  async function handleImport() {
    if (!importFile) { toast.error('Select a JSON file first.'); return; }
    try {
      await importMutation.trigger({ file: importFile });
      await characterMapQuery.mutate();
      setImportFile(null);
      toast.success('Characters imported.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Import failed');
    }
  }

  async function handleScrape() {
    if (!scrapeUrl.trim()) { toast.error('Enter a URL to scrape.'); return; }
    try {
      new URL(scrapeUrl);
    } catch {
      toast.error('Enter a valid URL.');
      return;
    }
    try {
      await scrapeMutation.trigger({ source_url: scrapeUrl.trim(), acknowledge_source_risk: true });
      await characterMapQuery.mutate();
      setScrapeUrl('');
      setActiveTool('none');
      toast.success('Characters scraped from URL.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Scrape failed');
    }
  }

  async function handleMerge() {
    try {
      await mergeMutation.trigger({ include_auto: true, acknowledge_source_risk: false });
      await characterMapQuery.mutate();
      toast.success('Character candidates merged.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Merge failed');
    }
  }

  async function handleInferGenders() {
    try {
      await inferGendersMutation.trigger();
      await characterMapQuery.mutate();
      toast.success('Gender inference complete.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Gender inference failed');
    }
  }

  async function handleFinalize() {
    try {
      await finalizeMutation.trigger();
      toast.success('Character map finalized.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Finalization failed');
    }
  }

  async function handleAliasLookup() {
    if (!aliasQuery.trim()) return;
    try {
      const result = await lookupAliasMutation.trigger({ alias: aliasQuery.trim() });
      setAliasResult({ canonical_name: result.canonical_name ?? null, match_source: result.match_source });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Alias lookup failed');
    }
  }

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Characters`}
      title="Characters"
      description="Review and manage character identities, genders, and aliases before voice assignment."
    >
      {/* Alias collisions warning */}
      {aliasCollisions.length > 0 && (
        <div className="rounded-xl border border-amber-400/20 bg-amber-400/5 p-4" data-testid="alias-collisions-warning">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 shrink-0 text-amber-400" size={15} />
            <div>
              <p className="text-sm font-medium text-amber-400">{aliasCollisions.length} alias collision{aliasCollisions.length > 1 ? 's' : ''} detected</p>
              <div className="mt-1 space-y-0.5">
                {aliasCollisions.map((c) => (
                  <p className="text-xs text-amber-400/80" key={c.alias}>
                    <span className="font-mono">{c.alias}</span> → {c.canonical_names.join(', ')}
                  </p>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Merge suggestions */}
      {mergeWarnings.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-card p-4" data-testid="merge-suggestions">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-foreground">{mergeWarnings.length} merge suggestion{mergeWarnings.length > 1 ? 's' : ''}</p>
            <Button
              data-testid="apply-merge-button"
              disabled={isBusy}
              onClick={() => void handleMerge()}
              size="sm"
              variant="outline"
            >
              <Merge size={13} />
              {mergeMutation.isMutating ? 'Merging…' : 'Apply Merge'}
            </Button>
          </div>
          <div className="mt-2 space-y-1">
            {mergeWarnings.slice(0, 5).map((suggestion, i) => (
              <p className="text-xs text-muted-foreground" key={i}>
                <span className="font-mono text-foreground">{suggestion.alias_name}</span>
                {' → '}
                <span className="font-mono text-foreground">{suggestion.canonical_name}</span>
                <span className="ml-2 text-muted-foreground/60">{suggestion.reason} ({Math.round(suggestion.score * 100)}%)</span>
              </p>
            ))}
            {mergeWarnings.length > 5 && <p className="text-xs text-muted-foreground">+{mergeWarnings.length - 5} more</p>}
          </div>
        </div>
      )}

      {/* Toolbar row */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Search */}
        <div className="relative min-w-0 flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={14} />
          <Input
            className="pl-9"
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search characters…"
            value={search}
          />
        </div>

        <div className="flex items-center gap-1.5 ml-auto">
          {/* Scrape from URL */}
          <Button
            className={cn(activeTool === 'scrape' && 'border-white/30 bg-white/5 text-foreground')}
            data-testid="toggle-scrape-tool"
            onClick={() => toggleTool('scrape')}
            size="sm"
            variant="outline"
          >
            <Globe size={13} />
            Scrape URL
          </Button>

          {/* Alias lookup */}
          <Button
            className={cn(activeTool === 'alias' && 'border-white/30 bg-white/5 text-foreground')}
            data-testid="toggle-alias-tool"
            onClick={() => toggleTool('alias')}
            size="sm"
            variant="outline"
          >
            <Search size={13} />
            Alias Lookup
          </Button>

          {/* Infer genders */}
          <Button
            data-testid="infer-genders-button"
            disabled={isBusy}
            onClick={() => void handleInferGenders()}
            size="sm"
            variant="outline"
          >
            <UserCheck size={13} />
            {inferGendersMutation.isMutating ? 'Inferring…' : 'Infer Genders'}
          </Button>
        </div>
      </div>

      {/* Scrape panel */}
      {activeTool === 'scrape' && (
        <div className="rounded-xl border border-white/10 bg-card p-4" data-testid="scrape-panel">
          <p className="mb-1 text-sm font-semibold text-foreground">Scrape characters from URL</p>
          <p className="mb-3 text-xs text-muted-foreground">
            Import characters from a fan wiki, character list page, or any public URL. The backend will extract character names from the page content.
          </p>
          <div className="flex gap-2">
            <Input
              autoFocus
              className="flex-1"
              data-testid="scrape-url-input"
              onChange={(e) => setScrapeUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void handleScrape()}
              placeholder="https://example.com/characters"
              type="url"
              value={scrapeUrl}
            />
            <Button
              data-testid="scrape-characters-button"
              disabled={isBusy || !scrapeUrl.trim()}
              onClick={() => void handleScrape()}
            >
              <Globe size={13} />
              {scrapeMutation.isMutating ? 'Scraping…' : 'Scrape'}
            </Button>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground/60">
            By proceeding you acknowledge the source content is used at your own risk.
          </p>
        </div>
      )}

      {/* Alias lookup panel */}
      {activeTool === 'alias' && (
        <div className="rounded-xl border border-white/10 bg-card p-4" data-testid="alias-lookup-panel">
          <p className="mb-1 text-sm font-semibold text-foreground">Alias Lookup</p>
          <p className="mb-3 text-xs text-muted-foreground">Resolve an alias or nickname to its canonical character name.</p>
          <div className="flex gap-2">
            <Input
              autoFocus
              className="flex-1"
              data-testid="alias-lookup-input"
              onChange={(e) => { setAliasQuery(e.target.value); setAliasResult(null); }}
              onKeyDown={(e) => e.key === 'Enter' && void handleAliasLookup()}
              placeholder="Enter alias to look up…"
              value={aliasQuery}
            />
            <Button
              data-testid="alias-lookup-button"
              disabled={lookupAliasMutation.isMutating || !aliasQuery.trim()}
              onClick={() => void handleAliasLookup()}
              variant="outline"
            >
              {lookupAliasMutation.isMutating ? 'Looking up…' : 'Look up'}
            </Button>
          </div>
          {aliasResult && (
            <p className="mt-3 text-sm" data-testid="alias-lookup-result">
              {aliasResult.canonical_name ? (
                <>
                  <span className="text-muted-foreground">Resolves to </span>
                  <span className="font-mono font-medium text-foreground">{aliasResult.canonical_name}</span>
                  <span className="ml-2 text-xs text-muted-foreground">via {aliasResult.match_source}</span>
                </>
              ) : (
                <span className="text-muted-foreground">No canonical match found for "{aliasQuery}"</span>
              )}
            </p>
          )}
        </div>
      )}

      {/* Gender comparison (shown when data is available) */}
      {genderComparisonQuery.data && genderComparisonQuery.data.comparisons.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-card p-4" data-testid="gender-comparison">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-semibold text-foreground">
              Gender Comparison
              {genderComparisonQuery.data.contradiction_count > 0 && (
                <span className="ml-2 text-xs font-normal text-amber-400">
                  <AlertTriangle className="inline mr-1" size={11} />
                  {genderComparisonQuery.data.contradiction_count} contradiction{genderComparisonQuery.data.contradiction_count > 1 ? 's' : ''}
                </span>
              )}
            </p>
          </div>
          <div className="max-h-40 overflow-y-auto divide-y divide-white/5">
            {genderComparisonQuery.data.comparisons.map((c) => (
              <div className="flex items-center gap-3 py-1.5 text-xs" key={c.name}>
                <span className="text-foreground w-36 truncate">{c.name}</span>
                <span className={cn('rounded-full px-1.5 py-0.5 font-medium capitalize', GENDER_BADGE[c.manual_gender])}>
                  {c.manual_gender}
                </span>
                {c.is_contradiction && (
                  <>
                    <span className="text-amber-400">≠</span>
                    <span className={cn('rounded-full px-1.5 py-0.5 font-medium capitalize', GENDER_BADGE[c.inferred_gender])}>
                      {c.inferred_gender} (inferred)
                    </span>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Table */}
      {characterMapQuery.isLoading && characters.length === 0 ? (
        <div className="space-y-2" data-testid="characters-loading">
          {Array.from({ length: 5 }).map((_, i) => (
            <div className="h-10 animate-pulse rounded-lg border border-white/5 bg-card" key={i} />
          ))}
        </div>
      ) : characters.length === 0 ? (
        <div className="rounded-xl border border-white/10 bg-card py-16 text-center" data-testid="characters-empty">
          <p className="text-sm font-medium text-foreground">No characters yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Extract characters from the uploaded source text, scrape from a URL, or import a JSON file.</p>
          <div className="mt-4 flex items-center justify-center gap-2">
            <Button
              data-testid="extract-characters-button-empty"
              disabled={isBusy}
              onClick={() => void handleExtract()}
            >
              <WandSparkles size={14} />
              {extractMutation.isMutating ? 'Extracting…' : 'Extract from text'}
            </Button>
            <Button
              disabled={isBusy}
              onClick={() => toggleTool('scrape')}
              variant="outline"
            >
              <Globe size={14} />
              Scrape URL
            </Button>
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-white/10 bg-card overflow-hidden" data-testid="characters-table">
          <div className="border-b border-white/10 px-4 py-2">
            <p className="text-xs text-muted-foreground">{characters.length} characters · {filtered.length} shown</p>
          </div>
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                {['Name', 'Aliases', 'Gender', 'Verbalized Form'].map((h) => (
                  <th
                    className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60"
                    key={h}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((character) => (
                <tr className="border-b border-white/5 transition-colors hover:bg-white/2" key={character.name}>
                  <td className="px-4 py-3">
                    <span className="text-sm font-medium text-foreground">{character.name}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-muted-foreground">
                      {character.aliases?.join(', ') || <span className="text-muted-foreground/30">—</span>}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn('inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize', GENDER_BADGE[character.gender ?? 'unknown'])}>
                      {character.gender ?? 'unknown'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs text-muted-foreground">{character.verbalized_form || '—'}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && search && (
            <p className="py-8 text-center text-sm text-muted-foreground">No characters match "{search}"</p>
          )}
        </div>
      )}

      {/* Floating action bar */}
      <div className="sticky bottom-0 flex flex-wrap items-center gap-3 rounded-xl border border-white/10 bg-card px-4 py-3 shadow-lg shadow-black/30">
        <Button
          data-testid="extract-characters-button"
          disabled={isBusy}
          onClick={() => void handleExtract()}
          size="sm"
          variant="outline"
        >
          <WandSparkles size={13} />
          {extractMutation.isMutating ? 'Extracting…' : 'Extract'}
        </Button>

        <div className="flex items-center gap-2">
          <label className="cursor-pointer" htmlFor="import-json">
            <span className={cn(
              'inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-md border border-white/15 bg-transparent px-3 text-xs font-medium text-muted-foreground transition-colors hover:border-white/25 hover:text-foreground',
              isBusy && 'pointer-events-none opacity-40',
            )}>
              <FileUp size={13} />
              Import JSON
            </span>
          </label>
          <input
            accept=".json"
            className="hidden"
            id="import-json"
            onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
            type="file"
          />
          {importFile && (
            <Button
              disabled={isBusy}
              onClick={() => void handleImport()}
              size="sm"
              variant="outline"
            >
              Upload: {importFile.name}
            </Button>
          )}
        </div>

        <Button
          className="ml-auto"
          data-testid="finalize-character-map-button"
          disabled={isBusy || characters.length === 0}
          onClick={() => void handleFinalize()}
          size="sm"
        >
          <CheckCheck size={13} />
          {finalizeMutation.isMutating ? 'Finalizing…' : 'Finalize Map'}
        </Button>
      </div>
    </WorkflowPageShell>
  );
}
