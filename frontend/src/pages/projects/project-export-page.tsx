import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Download, FileJson, FileSpreadsheet } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useExportPayloadQuery, useExportCsvMutation } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

export function ProjectExportPage() {
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const storeRunId = useWorkspaceStore((state) => state.runId);
  const projectId = routeProjectId ?? storeProjectId;
  const [runIdInput, setRunIdInput] = useState(storeRunId !== null ? String(storeRunId) : '');
  const [activeRunId, setActiveRunId] = useState<number | null>(storeRunId);

  const exportQuery = useExportPayloadQuery(projectId, activeRunId);
  const csvMutation = useExportCsvMutation(projectId, activeRunId);

  function loadRun() {
    const n = Number(runIdInput);
    if (!Number.isInteger(n) || n <= 0) { toast.error('Enter a valid run ID'); return; }
    setActiveRunId(n);
  }

  async function downloadJson() {
    if (!exportQuery.data) { toast.error('No export data available.'); return; }
    const blob = new Blob([JSON.stringify(exportQuery.data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nipe-export-run-${activeRunId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function downloadCsv() {
    try {
      const result = await csvMutation.trigger();
      const blob = new Blob([result], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `nipe-export-run-${activeRunId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'CSV export failed');
    }
  }

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Exports`}
      title="Exports"
      description="Download run outputs in JSON or CSV format for downstream processing."
    >
      {/* Run selector */}
      <div className="flex items-center gap-3">
        <Input
          className="w-36 font-mono"
          data-testid="export-run-id-input"
          onChange={(e) => setRunIdInput(e.target.value)}
          placeholder="Run ID"
          type="number"
          value={runIdInput}
        />
        <Button onClick={loadRun} size="sm" variant="outline">Load run</Button>
        {activeRunId && <span className="text-sm text-muted-foreground">Run #{activeRunId}</span>}
      </div>

      {activeRunId === null ? (
        <div className="rounded-xl border border-white/10 bg-card p-10 text-center" data-testid="export-no-run">
          <p className="text-sm text-muted-foreground">Enter a run ID to load export options.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2" data-testid="export-download-cards">
          {/* JSON */}
          <div className={cn(
            'flex flex-col gap-4 rounded-xl border border-white/10 bg-card p-5 transition-colors',
            exportQuery.data ? 'hover:border-white/20' : 'opacity-50',
          )}>
            <div className="flex items-center gap-3">
              <div className="grid size-9 place-items-center rounded-lg border border-white/10 bg-white/5 text-muted-foreground">
                <FileJson size={18} />
              </div>
              <div>
                <p className="font-medium text-foreground">JSON Export</p>
                <p className="text-xs text-muted-foreground">Full structured output</p>
              </div>
            </div>
            {exportQuery.data && (
              <p className="text-xs text-muted-foreground">
                {JSON.stringify(exportQuery.data).length.toLocaleString()} characters
              </p>
            )}
            <Button
              className="mt-auto"
              data-testid="download-json-button"
              disabled={!exportQuery.data || exportQuery.isLoading}
              onClick={() => void downloadJson()}
              variant="outline"
            >
              <Download size={14} />
              {exportQuery.isLoading ? 'Loading…' : 'Download JSON'}
            </Button>
          </div>

          {/* CSV */}
          <div className="flex flex-col gap-4 rounded-xl border border-white/10 bg-card p-5 transition-colors hover:border-white/20">
            <div className="flex items-center gap-3">
              <div className="grid size-9 place-items-center rounded-lg border border-white/10 bg-white/5 text-muted-foreground">
                <FileSpreadsheet size={18} />
              </div>
              <div>
                <p className="font-medium text-foreground">CSV Export</p>
                <p className="text-xs text-muted-foreground">Tabular format for spreadsheets</p>
              </div>
            </div>
            <Button
              className="mt-auto"
              data-testid="download-csv-button"
              disabled={csvMutation.isMutating}
              onClick={() => void downloadCsv()}
              variant="outline"
            >
              <Download size={14} />
              {csvMutation.isMutating ? 'Generating…' : 'Download CSV'}
            </Button>
          </div>
        </div>
      )}
    </WorkflowPageShell>
  );
}
