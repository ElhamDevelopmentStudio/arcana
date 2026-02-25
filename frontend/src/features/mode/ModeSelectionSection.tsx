import type { ModeCatalog } from "@/app/types";
import Button from "@/shared/ui/Button";
import Card from "@/shared/ui/Card";
import { SelectField } from "@/shared/ui/Field";
import StatusChip from "@/shared/ui/StatusChip";

type ModeSelectionSectionProps = {
  loading: boolean;
  canSelectMode: boolean;
  modeOptions: string[];
  selectedMode: string;
  onSelectedModeChange: (mode: string) => void;
  modeCatalog: ModeCatalog | null;
  projectMode: string | null;
  runMode: string | null;
};

function ModeSelectionSection({
  loading,
  canSelectMode,
  modeOptions,
  selectedMode,
  onSelectedModeChange,
  modeCatalog,
  projectMode,
  runMode,
}: ModeSelectionSectionProps) {
  return (
    <Card
      title="2) Mode Selection (Post-Ingestion)"
      subtitle="Mode selection stays locked until ingestion completes successfully."
      testId="mode-selection-section"
      action={
        canSelectMode ? <StatusChip tone="success">Selectable</StatusChip> : <StatusChip tone="danger">Locked</StatusChip>
      }
    >
      <SelectField
        label="Processing mode"
        value={selectedMode}
        data-testid="mode-select"
        disabled={loading || !canSelectMode}
        onChange={(event) => onSelectedModeChange(event.target.value)}
        hint={canSelectMode ? "Mode is snapshotted into run config." : "Upload TXT first to unlock mode selection."}
      >
        {modeOptions.map((mode) => (
          <option key={mode} value={mode}>
            {mode}
          </option>
        ))}
      </SelectField>

      <div className="ui-form-row">
        <StatusChip tone="neutral">Project selected mode: {projectMode ?? "unknown"}</StatusChip>
        <StatusChip tone="accent">Latest run mode: {runMode ?? "not run yet"}</StatusChip>
        {modeCatalog ? <StatusChip>Persistence: {modeCatalog.persisted_in.join(" | ")}</StatusChip> : null}
      </div>

      <Button disabled={!canSelectMode || loading} variant="secondary" type="button">
        Confirm Mode for Next Run
      </Button>
    </Card>
  );
}

export default ModeSelectionSection;
