import type { ExportPayload, RunDetail } from "@/app/types";
import { formatTimestamp } from "@/shared/lib/time";
import Button from "@/shared/ui/Button";
import Card from "@/shared/ui/Card";
import StatusChip from "@/shared/ui/StatusChip";

type RunArtifactsSectionProps = {
  loading: boolean;
  projectId: number | null;
  runId: number | null;
  runDetail: RunDetail | null;
  exportPayload: ExportPayload | null;
  onRefreshRun: () => void;
};

function RunArtifactsSection({
  loading,
  projectId,
  runId,
  runDetail,
  exportPayload,
  onRefreshRun,
}: RunArtifactsSectionProps) {
  return (
    <Card
      title="5) Run Artifacts + Export"
      subtitle="Inspect run details, provider activity, and final TTS-ready export payload."
      testId="run-artifacts-section"
      action={runId ? <StatusChip tone="accent">Run #{runId}</StatusChip> : <StatusChip>Run pending</StatusChip>}
    >
      <div className="ui-form-row">
        <Button disabled={loading || !projectId || !runId} onClick={onRefreshRun} type="button">
          Refresh Run Artifacts
        </Button>
      </div>

      {runDetail ? (
        <div className="ui-panel">
          <h3>Run Status</h3>
          <div className="meta-grid">
            <div>
              <strong>Status:</strong> {runDetail.status}
            </div>
            <div>
              <strong>Started:</strong> {formatTimestamp(runDetail.started_at)}
            </div>
            <div>
              <strong>Finished:</strong> {formatTimestamp(runDetail.finished_at)}
            </div>
            <div>
              <strong>Segments:</strong> {runDetail.segment_count}
            </div>
          </div>
          <pre>{JSON.stringify(runDetail, null, 2)}</pre>
        </div>
      ) : null}

      {exportPayload ? (
        <div className="ui-panel">
          <h3>Export JSON</h3>
          <pre>{JSON.stringify(exportPayload, null, 2)}</pre>
        </div>
      ) : null}
    </Card>
  );
}

export default RunArtifactsSection;
