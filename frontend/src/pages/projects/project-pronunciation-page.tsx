import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Plus, Trash2, Eye } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  useArtifactPronunciationDictionaryQuery,
  useInventedPronunciationDictionaryQuery,
  useGlobalPronunciationDictionaryQuery,
  usePlacePronunciationDictionaryQuery,
  useSaveArtifactPronunciationDictionaryMutation,
  useSaveInventedPronunciationDictionaryMutation,
  useSaveGlobalPronunciationDictionaryMutation,
  useSavePlacePronunciationDictionaryMutation,
  usePronunciationPreviewMutation,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { cn } from '@/lib/utils';

type DictEntry = { term: string; verbalized_form: string; source: string; confidence: number };

type DictScope = 'artifact' | 'invented' | 'global' | 'place';

const SCOPE_META: Record<DictScope, { label: string; description: string; color: string }> = {
  artifact: { label: 'Artifacts', description: 'Named items, weapons, relics, and created objects', color: 'text-blue-400' },
  invented: { label: 'Invented Words', description: 'Neologisms, portmanteaus, and made-up terms', color: 'text-purple-400' },
  global: { label: 'Global', description: 'Universal pronunciation rules applied to all text', color: 'text-green-400' },
  place: { label: 'Places', description: 'Location names, worlds, cities, and geography', color: 'text-amber-400' },
};

function DictionaryTable({
  entries,
  onAdd,
  onChange,
  onRemove,
  isBusy,
}: {
  entries: DictEntry[];
  onAdd: () => void;
  onChange: (index: number, field: keyof DictEntry, value: string | number) => void;
  onRemove: (index: number) => void;
  isBusy: boolean;
}) {
  if (entries.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-muted-foreground">No entries. Add one below.</p>
        <Button className="mt-3" disabled={isBusy} onClick={onAdd} size="sm" variant="outline">
          <Plus size={13} /> Add Entry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="grid grid-cols-[1fr_1fr_auto] gap-2 px-1 pb-1">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">Term</span>
        <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">Verbalized Form</span>
        <span className="w-8" />
      </div>
      {entries.map((entry, i) => (
        <div className="grid grid-cols-[1fr_1fr_auto] items-center gap-2" key={i}>
          <Input
            className="text-sm"
            disabled={isBusy}
            onChange={(e) => onChange(i, 'term', e.target.value)}
            placeholder="e.g. LLM"
            value={entry.term}
          />
          <Input
            className="text-sm"
            disabled={isBusy}
            onChange={(e) => onChange(i, 'verbalized_form', e.target.value)}
            placeholder="e.g. Large Language Model"
            value={entry.verbalized_form}
          />
          <button
            aria-label="Remove entry"
            className="grid size-8 place-items-center rounded-md text-muted-foreground/40 transition-colors hover:text-red-400"
            disabled={isBusy}
            onClick={() => onRemove(i)}
            type="button"
          >
            <Trash2 size={13} />
          </button>
        </div>
      ))}
      <Button className="mt-2" disabled={isBusy} onClick={onAdd} size="sm" variant="outline">
        <Plus size={13} /> Add Entry
      </Button>
    </div>
  );
}

function DictionarySection({
  scope,
  projectId,
}: {
  scope: DictScope;
  projectId: number | null;
}) {
  const meta = SCOPE_META[scope];

  const queryMap = {
    artifact: useArtifactPronunciationDictionaryQuery(projectId),
    invented: useInventedPronunciationDictionaryQuery(projectId),
    global: useGlobalPronunciationDictionaryQuery(projectId),
    place: usePlacePronunciationDictionaryQuery(projectId),
  };
  const saveMap = {
    artifact: useSaveArtifactPronunciationDictionaryMutation(projectId),
    invented: useSaveInventedPronunciationDictionaryMutation(projectId),
    global: useSaveGlobalPronunciationDictionaryMutation(projectId),
    place: useSavePlacePronunciationDictionaryMutation(projectId),
  };

  const query = queryMap[scope];
  const saveMutation = saveMap[scope];

  const [localEntries, setLocalEntries] = useState<DictEntry[] | null>(null);
  const entries: DictEntry[] = localEntries ?? (query.data?.entries ?? []).map((e) => ({ ...e }));

  function addEntry() {
    setLocalEntries([...entries, { term: '', verbalized_form: '', source: 'user', confidence: 1.0 }]);
  }

  function changeEntry(i: number, field: keyof DictEntry, value: string | number) {
    const next = entries.map((e, idx) => idx === i ? { ...e, [field]: value } : e);
    setLocalEntries(next);
  }

  function removeEntry(i: number) {
    setLocalEntries(entries.filter((_, idx) => idx !== i));
  }

  async function handleSave() {
    try {
      const valid = entries.filter((e) => e.term.trim() && e.verbalized_form.trim());
      await saveMutation.trigger({ entries: valid.map((e) => ({ ...e, source: 'user', confidence: 1.0 })) });
      toast.success(`${meta.label} dictionary saved.`);
      setLocalEntries(null);
      await query.mutate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Save failed');
    }
  }

  const isDirty = localEntries !== null;
  const isBusy = saveMutation.isMutating;

  return (
    <div className="rounded-xl border border-white/10 bg-card p-5" data-testid={`pronunciation-section-${scope}`}>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className={cn('text-sm font-semibold', meta.color)}>{meta.label}</p>
          <p className="text-xs text-muted-foreground">{meta.description}</p>
        </div>
        {isDirty && (
          <Button disabled={isBusy} onClick={() => void handleSave()} size="sm">
            {isBusy ? 'Saving…' : 'Save'}
          </Button>
        )}
      </div>

      {query.isLoading ? (
        <div className="space-y-2">
          {[1, 2].map((i) => <div className="h-8 animate-pulse rounded-lg bg-white/5" key={i} />)}
        </div>
      ) : (
        <DictionaryTable
          entries={entries}
          isBusy={isBusy}
          onAdd={addEntry}
          onChange={changeEntry}
          onRemove={removeEntry}
        />
      )}
    </div>
  );
}

export function ProjectPronunciationPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;

  const previewMutation = usePronunciationPreviewMutation(projectId);
  const [previewText, setPreviewText] = useState('');
  const [previewResult, setPreviewResult] = useState<{ before: string; after: string; replacements: Array<{ term: string; verbalized_form: string; count: number; scope: string }> } | null>(null);

  async function handlePreview() {
    if (!previewText.trim()) { toast.error('Enter some text to preview.'); return; }
    try {
      const result = await previewMutation.trigger({
        text: previewText,
        include_global_scope: true,
        include_character_scope: false,
        include_place_scope: true,
        include_artifact_scope: true,
        include_invented_scope: true,
        match_whole_words: true,
        case_sensitive: true,
        alias_aware: false,
      });
      setPreviewResult(result);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Preview failed');
    }
  }

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Pronunciation`}
      title="Pronunciation Dictionaries"
      description="Define how terms should be verbalized by the TTS engine. Each dictionary scope applies to different categories of text."
    >
      <div className="space-y-4 max-w-3xl">
        {(['artifact', 'invented', 'global', 'place'] as DictScope[]).map((scope) => (
          <DictionarySection key={scope} projectId={projectId} scope={scope} />
        ))}

        {/* Preview panel */}
        <div className="rounded-xl border border-white/10 bg-card p-5" data-testid="pronunciation-preview-panel">
          <p className="mb-1 text-sm font-semibold text-foreground">Preview</p>
          <p className="mb-3 text-xs text-muted-foreground">Test how your dictionaries transform a sample text passage.</p>
          <Textarea
            className="mb-3 min-h-[80px] resize-y"
            onChange={(e) => setPreviewText(e.target.value)}
            placeholder="Paste a sample paragraph to see how pronunciation rules are applied…"
            value={previewText}
          />
          <Button
            data-testid="pronunciation-preview-button"
            disabled={previewMutation.isMutating || !previewText.trim()}
            onClick={() => void handlePreview()}
            size="sm"
            variant="outline"
          >
            <Eye size={13} />
            {previewMutation.isMutating ? 'Previewing…' : 'Preview'}
          </Button>

          {previewResult && (
            <div className="mt-4 space-y-3" data-testid="pronunciation-preview-result">
              <div className="rounded-lg border border-white/10 bg-white/2 p-3">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">Before</p>
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">{previewResult.before}</p>
              </div>
              <div className="rounded-lg border border-green-400/20 bg-green-400/5 p-3">
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-green-400/60">After</p>
                <p className="whitespace-pre-wrap text-sm text-foreground">{previewResult.after}</p>
              </div>
              {previewResult.replacements.length > 0 && (
                <div className="space-y-1">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">Replacements ({previewResult.replacements.length})</p>
                  {previewResult.replacements.map((r, i) => (
                    <div className="flex items-center gap-3 text-xs" key={i}>
                      <span className="font-mono text-foreground">{r.term}</span>
                      <span className="text-muted-foreground">→</span>
                      <span className="font-mono text-green-400">{r.verbalized_form}</span>
                      <span className="ml-auto text-muted-foreground">{r.scope} · ×{r.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </WorkflowPageShell>
  );
}
