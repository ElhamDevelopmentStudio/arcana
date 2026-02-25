import { type FormEvent, useMemo, useState } from 'react';

import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

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
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Import</CardTitle>
            <CardDescription>Upload a character map file and apply it to this project.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
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
            </form>
            <p className="text-sm text-muted-foreground" data-testid="character-import-state">
              {importedCount !== null ? `Imported rows: ${importedCount}` : 'No import completed yet.'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Manual Editor</CardTitle>
            <CardDescription>Add/edit/delete rows locally. Backend save endpoint will be connected when available.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid max-h-72 gap-2 overflow-auto pr-1">
              {manualRows.map((row) => (
                <div key={row.id} className="grid gap-2 rounded-lg border p-2">
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
                  <div className="flex gap-2">
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
            <div className="flex items-center justify-between">
              <Button variant="outline" onClick={addRow} type="button">
                Add Row
              </Button>
              <Badge variant="secondary">Ready rows: {manualPreviewCount}</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Scrape</CardTitle>
            <CardDescription>Gather candidates from external sources only with explicit legal acknowledgement.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            {appEnv.featureScrapeEnabled ? (
              <>
                <p>Scrape feature flag is enabled in environment.</p>
                <Button variant="outline" type="button">
                  Open scrape flow (placeholder)
                </Button>
              </>
            ) : (
              <>
                <Badge variant="outline">Disabled by environment flag</Badge>
                <p>Enable with `VITE_FEATURE_SCRAPE_ENABLED=true` once backend scrape APIs are implemented.</p>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </WorkflowPageShell>
  );
}
