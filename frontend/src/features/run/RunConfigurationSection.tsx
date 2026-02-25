import type { FormEvent } from "react";

import Button from "@/shared/ui/Button";
import Card from "@/shared/ui/Card";
import { TextField } from "@/shared/ui/Field";

type RunConfigurationSectionProps = {
  loading: boolean;
  canRun: boolean;
  narratorVoice: string;
  maleVoice: string;
  femaleVoice: string;
  maxSegmentChars: number;
  llmEnabled: boolean;
  providerName: string;
  maxCallsPerDay: number;
  onNarratorVoiceChange: (value: string) => void;
  onMaleVoiceChange: (value: string) => void;
  onFemaleVoiceChange: (value: string) => void;
  onMaxSegmentCharsChange: (value: number) => void;
  onLlmEnabledChange: (value: boolean) => void;
  onProviderNameChange: (value: string) => void;
  onMaxCallsPerDayChange: (value: number) => void;
  onSaveVoices: (event: FormEvent) => void;
  onRunPipeline: (event: FormEvent) => void;
};

function RunConfigurationSection({
  loading,
  canRun,
  narratorVoice,
  maleVoice,
  femaleVoice,
  maxSegmentChars,
  llmEnabled,
  providerName,
  maxCallsPerDay,
  onNarratorVoiceChange,
  onMaleVoiceChange,
  onFemaleVoiceChange,
  onMaxSegmentCharsChange,
  onLlmEnabledChange,
  onProviderNameChange,
  onMaxCallsPerDayChange,
  onSaveVoices,
  onRunPipeline,
}: RunConfigurationSectionProps) {
  return (
    <Card
      title="4) Voice + Pipeline Run"
      subtitle="Configure voices and run settings, then execute pipeline for current project + selected mode."
      testId="run-configuration-section"
    >
      <form onSubmit={onSaveVoices} className="ui-grid-4">
        <TextField label="Narrator voice" value={narratorVoice} onChange={(event) => onNarratorVoiceChange(event.target.value)} />
        <TextField label="Male default voice" value={maleVoice} onChange={(event) => onMaleVoiceChange(event.target.value)} />
        <TextField
          label="Female default voice"
          value={femaleVoice}
          onChange={(event) => onFemaleVoiceChange(event.target.value)}
        />
        <Button disabled={loading || !canRun} type="submit">
          Save Voices
        </Button>
      </form>

      <form onSubmit={onRunPipeline} className="ui-grid-4">
        <TextField
          label="Max segment chars"
          type="number"
          min={80}
          max={255}
          value={maxSegmentChars}
          onChange={(event) => onMaxSegmentCharsChange(Number(event.target.value))}
        />

        <label className="ui-field">
          <span className="ui-field__label">LLM enabled</span>
          <input className="ui-checkbox" type="checkbox" checked={llmEnabled} onChange={(event) => onLlmEnabledChange(event.target.checked)} />
        </label>

        <TextField label="Provider" value={providerName} onChange={(event) => onProviderNameChange(event.target.value)} />

        <TextField
          label="Max calls/day"
          type="number"
          min={1}
          value={maxCallsPerDay}
          onChange={(event) => onMaxCallsPerDayChange(Number(event.target.value))}
        />

        <Button disabled={loading || !canRun} type="submit">
          Run Pipeline
        </Button>
      </form>
    </Card>
  );
}

export default RunConfigurationSection;
