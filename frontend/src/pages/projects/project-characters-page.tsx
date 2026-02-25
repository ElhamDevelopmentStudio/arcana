import { type FormEvent, useMemo, useState } from 'react';

import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { AlertCircle, FileUp, Plus, UserCog, WandSparkles } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { appEnv } from '@/app/config/env';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import { useImportCharactersMutation } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam, projectRoute } from '@/features/workflow/utils/project-route';

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

export function ProjectCharactersPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;

  const importCharactersMutation = useImportCharactersMutation(projectId);
  const [characterFile, setCharacterFile] = useState<File | null>(null);
  const [importedCount, setImportedCount] = useState<number | null>(null);

  const [manualRows, setManualRows] = useState<ManualCharacterRow[]>([createRow()]);
  const manualPreviewCount = useMemo(
    () => manualRows.filter((row) => row.name.trim() && row.verbalized.trim()).length,
    [manualRows],
  );

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
      toast.success(`Imported ${payload.imported_count} character rows.`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Character import failed.');
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
              <p className="flex items-center gap-2 font-medium text-foreground">
                <WandSparkles className="size-4 text-primary" />
                Scrape candidates
              </p>
              {appEnv.featureScrapeEnabled ? (
                <Button variant="outline" type="button">
                  Open scrape flow (placeholder)
                </Button>
              ) : (
                <div className="space-y-2">
                  <p className="inline-flex items-center gap-1 text-xs font-medium uppercase tracking-[0.08em]">
                    <AlertCircle className="size-3.5 text-muted-foreground" />
                    Disabled by environment flag
                  </p>
                  <p>Enable with `VITE_FEATURE_SCRAPE_ENABLED=true` once backend scrape APIs are implemented.</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserCog className="size-4 text-primary" />
              Manual Editor
            </CardTitle>
            <CardDescription>Add, adjust, and remove rows locally before backend save integration.</CardDescription>
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
              <p className="text-sm text-muted-foreground">Ready rows: {manualPreviewCount}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </WorkflowPageShell>
  );
}
