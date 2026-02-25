import type { FormEvent } from "react";

import type { IngestionSource } from "@/app/types";
import Button from "@/shared/ui/Button";
import Card from "@/shared/ui/Card";
import { SelectField, TextField } from "@/shared/ui/Field";
import StatusChip from "@/shared/ui/StatusChip";

type ProjectSetupSectionProps = {
  loading: boolean;
  projectTitle: string;
  onProjectTitleChange: (value: string) => void;
  onCreateProject: (event: FormEvent) => void;
  projectId: number | null;
  ingestionSource: IngestionSource;
  onIngestionSourceChange: (value: IngestionSource) => void;
  txtFile: File | null;
  onTxtFileChange: (file: File | null) => void;
  onUploadTxt: (event: FormEvent) => void;
  canRun: boolean;
  ingestedChapterCount: number | null;
};

function ProjectSetupSection({
  loading,
  projectTitle,
  onProjectTitleChange,
  onCreateProject,
  projectId,
  ingestionSource,
  onIngestionSourceChange,
  txtFile,
  onTxtFileChange,
  onUploadTxt,
  canRun,
  ingestedChapterCount,
}: ProjectSetupSectionProps) {
  return (
    <Card
      title="1) Project Setup + Ingestion"
      subtitle="Current backend supports TXT ingestion. Other sources are scaffolded for near-term extension."
      testId="project-setup-section"
      action={projectId ? <StatusChip tone="success">Project #{projectId}</StatusChip> : <StatusChip>Not created</StatusChip>}
    >
      <form onSubmit={onCreateProject} className="ui-form-row">
        <TextField
          label="Project title"
          value={projectTitle}
          placeholder="Shadow Slave PoC"
          onChange={(event) => onProjectTitleChange(event.target.value)}
        />
        <Button disabled={loading} type="submit">
          Create Project
        </Button>
      </form>

      <form onSubmit={onUploadTxt} className="ui-grid-2">
        <SelectField
          label="Ingestion source"
          value={ingestionSource}
          onChange={(event) => onIngestionSourceChange(event.target.value as IngestionSource)}
          hint={ingestionSource === "txt" ? "Active source" : "Selected source is currently blocked by backend support"}
        >
          <option value="txt">TXT file (active)</option>
          <option value="directory">Chapter directory (pending)</option>
          <option value="markdown">Markdown (pending)</option>
          <option value="epub">EPUB (pending)</option>
        </SelectField>

        <label className="ui-field">
          <span className="ui-field__label">TXT file</span>
          <input
            className="ui-input"
            type="file"
            accept=".txt"
            onChange={(event) => onTxtFileChange(event.target.files?.[0] ?? null)}
          />
          <span className="ui-field__hint">
            {txtFile ? `Selected: ${txtFile.name}` : "Choose a source file to ingest chapters."}
          </span>
        </label>

        <div className="ui-form-row">
          <Button disabled={loading || !canRun || !txtFile || ingestionSource !== "txt"} type="submit">
            Upload TXT
          </Button>
          {ingestedChapterCount !== null ? (
            <StatusChip tone="accent">Detected chapters: {ingestedChapterCount}</StatusChip>
          ) : (
            <StatusChip>Awaiting ingestion</StatusChip>
          )}
        </div>
      </form>
    </Card>
  );
}

export default ProjectSetupSection;
