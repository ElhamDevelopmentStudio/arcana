import type { FormEvent } from "react";

import Button from "@/shared/ui/button";
import Card from "@/shared/ui/card";
import StatusChip from "@/shared/ui/status-chip";

type CharacterImportSectionProps = {
  loading: boolean;
  canRun: boolean;
  characterFile: File | null;
  onCharacterFileChange: (file: File | null) => void;
  onUploadCharacters: (event: FormEvent) => void;
  importedCount: number | null;
};

function CharacterImportSection({
  loading,
  canRun,
  characterFile,
  onCharacterFileChange,
  onUploadCharacters,
  importedCount,
}: CharacterImportSectionProps) {
  return (
    <Card
      title="3) Character Map Import"
      subtitle="Import JSON/CSV map for pronunciation, gender, and voice-aware downstream processing."
      testId="character-import-section"
      action={<StatusChip tone={importedCount ? "success" : "neutral"}>{importedCount ?? 0} imported</StatusChip>}
    >
      <form onSubmit={onUploadCharacters} className="ui-form-row">
        <label className="ui-field">
          <span className="ui-field__label">Character map file</span>
          <input
            className="ui-input"
            type="file"
            accept=".json,.csv"
            onChange={(event) => onCharacterFileChange(event.target.files?.[0] ?? null)}
          />
          <span className="ui-field__hint">{characterFile ? characterFile.name : "Use PoC-compatible schema."}</span>
        </label>

        <Button disabled={loading || !canRun || !characterFile} type="submit">
          Import Character Map
        </Button>
      </form>
    </Card>
  );
}

export default CharacterImportSection;
