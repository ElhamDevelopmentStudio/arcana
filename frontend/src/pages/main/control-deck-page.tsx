import { FormEvent, Suspense, lazy, useEffect, useMemo, useState } from "react";

import { getInitialApiBaseUrl } from "@/app/config/env";
import { useUiStore } from "@/app/store/ui-store";
import type { ExportPayload, IngestionSource, ProjectRecord, RunDetail } from "@/app/types";
import PageHeader from "@/features/layout/page-header";
import { pickModeFromCatalog, resolveModeOptions } from "@/features/mode/mode-catalog";
import { useModeCatalog } from "@/features/mode/use-mode-catalog";
import ToastStack from "@/features/notifications/toast-stack";
import { NipeApiClient } from "@/shared/api/http";
import Button from "@/shared/ui/button";
import Card from "@/shared/ui/card";
import { TextField } from "@/shared/ui/field";
import StatusChip from "@/shared/ui/status-chip";

const ProjectSetupSection = lazy(() => import("@/features/project/project-setup-section"));
const ModeSelectionSection = lazy(() => import("@/features/mode/mode-selection-section"));
const CharacterImportSection = lazy(() => import("@/features/character/character-import-section"));
const RunConfigurationSection = lazy(() => import("@/features/run/run-configuration-section"));
const RunArtifactsSection = lazy(() => import("@/features/export/run-artifacts-section"));

function SectionFallback() {
  return <div className="section-fallback">Loading section…</div>;
}

function ControlDeckPage() {
  const [apiBase, setApiBase] = useState(getInitialApiBaseUrl());
  const [projectTitle, setProjectTitle] = useState("Shadow Slave PoC");
  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [ingestedChapterCount, setIngestedChapterCount] = useState<number | null>(null);
  const [runId, setRunId] = useState<number | null>(null);
  const [txtFile, setTxtFile] = useState<File | null>(null);
  const [charFile, setCharFile] = useState<File | null>(null);
  const [selectedMode, setSelectedMode] = useState<string>("audiobook");
  const [ingestionSource, setIngestionSource] = useState<IngestionSource>("txt");

  const [narratorVoice, setNarratorVoice] = useState("narrator_default");
  const [maleVoice, setMaleVoice] = useState("male_default");
  const [femaleVoice, setFemaleVoice] = useState("female_default");

  const [maxSegmentChars, setMaxSegmentChars] = useState(255);
  const [llmEnabled, setLlmEnabled] = useState(false);
  const [providerName, setProviderName] = useState("openrouter");
  const [maxCallsPerDay, setMaxCallsPerDay] = useState(25);

  const [runDetail, setRunDetail] = useState<RunDetail | null>(null);
  const [exportPayload, setExportPayload] = useState<ExportPayload | null>(null);
  const [importedCount, setImportedCount] = useState<number | null>(null);

  const isBusy = useUiStore((state) => state.isBusy);
  const setBusy = useUiStore((state) => state.setBusy);
  const pushMessage = useUiStore((state) => state.pushMessage);

  const apiClient = useMemo(() => new NipeApiClient(apiBase), [apiBase]);
  const { catalog: modeCatalog, error: modeCatalogError, mutate: refreshModeCatalog } = useModeCatalog(
    apiClient,
    project !== null
  );

  useEffect(() => {
    if (!modeCatalog) {
      return;
    }

    setSelectedMode((current) => pickModeFromCatalog(modeCatalog, current));
  }, [modeCatalog]);

  useEffect(() => {
    if (!modeCatalogError) {
      return;
    }

    pushMessage({
      kind: "error",
      title: "Mode catalog fetch failed",
      detail: modeCatalogError.message,
    });
  }, [modeCatalogError, pushMessage]);

  const canRun = project !== null;
  const canSelectMode = project !== null && ingestedChapterCount !== null;
  const modeOptions = useMemo(() => resolveModeOptions(modeCatalog), [modeCatalog]);
  const runModeFromConfig = typeof runDetail?.config.mode === "string" ? runDetail.config.mode : null;

  async function withBusy(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  }

  async function createProject(event: FormEvent) {
    event.preventDefault();

    await withBusy(async () => {
      try {
        const record = await apiClient.createProject(projectTitle);
        setProject(record);
        setIngestedChapterCount(null);
        setRunId(null);
        setRunDetail(null);
        setExportPayload(null);
        setImportedCount(null);
        setSelectedMode(record.selected_mode);
        await refreshModeCatalog();
        pushMessage({ kind: "success", title: `Project created`, detail: `Project ID: ${record.id}` });
      } catch (error) {
        pushMessage({
          kind: "error",
          title: "Failed to create project",
          detail: error instanceof Error ? error.message : "Unknown error",
        });
      }
    });
  }

  async function uploadTxt(event: FormEvent) {
    event.preventDefault();

    if (!project || !txtFile) {
      return;
    }

    if (ingestionSource !== "txt") {
      pushMessage({
        kind: "info",
        title: "Ingestion source blocked",
        detail: "Backend currently supports TXT ingestion only.",
      });
      return;
    }

    await withBusy(async () => {
      try {
        const payload = await apiClient.ingestTxt(project.id, txtFile);
        setIngestedChapterCount(payload.chapter_count);
        await refreshModeCatalog();
        pushMessage({
          kind: "success",
          title: "TXT ingested",
          detail: `Chapters detected: ${payload.chapter_count}`,
        });
      } catch (error) {
        pushMessage({
          kind: "error",
          title: "TXT ingestion failed",
          detail: error instanceof Error ? error.message : "Unknown error",
        });
      }
    });
  }

  async function uploadCharacters(event: FormEvent) {
    event.preventDefault();
    if (!project || !charFile) {
      return;
    }

    await withBusy(async () => {
      try {
        const payload = await apiClient.importCharacters(project.id, charFile);
        setImportedCount(payload.imported_count);
        pushMessage({
          kind: "success",
          title: "Character map imported",
          detail: `Rows imported: ${payload.imported_count}`,
        });
      } catch (error) {
        pushMessage({
          kind: "error",
          title: "Character import failed",
          detail: error instanceof Error ? error.message : "Unknown error",
        });
      }
    });
  }

  async function saveVoices(event: FormEvent) {
    event.preventDefault();
    if (!project) {
      return;
    }

    await withBusy(async () => {
      try {
        await apiClient.saveVoices(project.id, {
          narrator_voice: narratorVoice,
          male_default_voice: maleVoice,
          female_default_voice: femaleVoice,
        });

        pushMessage({ kind: "success", title: "Voice config saved" });
      } catch (error) {
        pushMessage({
          kind: "error",
          title: "Failed to save voices",
          detail: error instanceof Error ? error.message : "Unknown error",
        });
      }
    });
  }

  async function refreshRunArtifacts(projectId: number, currentRunId: number) {
    const [runPayload, exportJson] = await Promise.all([
      apiClient.getRunDetail(projectId, currentRunId),
      apiClient.getExport(projectId, currentRunId),
    ]);

    setRunDetail(runPayload);
    setExportPayload(exportJson);
  }

  async function runPipeline(event: FormEvent) {
    event.preventDefault();
    if (!project) {
      return;
    }

    await withBusy(async () => {
      try {
        const runPayload = await apiClient.runPipeline(project.id, {
          mode: selectedMode,
          max_segment_chars: maxSegmentChars,
          llm_enabled: llmEnabled,
          provider_name: providerName,
          max_calls_per_day: maxCallsPerDay,
        });

        setRunId(runPayload.run_id);
        await refreshRunArtifacts(project.id, runPayload.run_id);
        pushMessage({
          kind: "success",
          title: "Pipeline finished",
          detail: `Segments produced: ${runPayload.segment_count}`,
        });
      } catch (error) {
        pushMessage({
          kind: "error",
          title: "Pipeline run failed",
          detail: error instanceof Error ? error.message : "Unknown error",
        });
      }
    });
  }

  async function refreshCurrentRun() {
    if (!project || !runId) {
      return;
    }

    await withBusy(async () => {
      try {
        await refreshRunArtifacts(project.id, runId);
        pushMessage({ kind: "success", title: "Run artifacts refreshed" });
      } catch (error) {
        pushMessage({
          kind: "error",
          title: "Run refresh failed",
          detail: error instanceof Error ? error.message : "Unknown error",
        });
      }
    });
  }

  return (
    <div className="app-root" aria-busy={isBusy}>
      <div className="bg-orb bg-orb--a" aria-hidden="true" />
      <div className="bg-orb bg-orb--b" aria-hidden="true" />

      <div className="shell-grid">
        <PageHeader />

        <Card title="Connection" subtitle="Backend target and current execution state." testId="connection-section">
          <div className="ui-grid-2">
            <TextField label="API Base URL" value={apiBase} onChange={(event) => setApiBase(event.target.value)} />
            <div className="ui-form-row">
              <StatusChip tone={isBusy ? "danger" : "success"}>{isBusy ? "Busy" : "Idle"}</StatusChip>
              <Button
                variant="secondary"
                type="button"
                onClick={() => {
                  void refreshModeCatalog();
                }}
              >
                Refresh Modes
              </Button>
            </div>
          </div>
        </Card>

        <Suspense fallback={<SectionFallback />}>
          <ProjectSetupSection
            loading={isBusy}
            projectTitle={projectTitle}
            onProjectTitleChange={setProjectTitle}
            onCreateProject={createProject}
            projectId={project?.id ?? null}
            ingestionSource={ingestionSource}
            onIngestionSourceChange={setIngestionSource}
            txtFile={txtFile}
            onTxtFileChange={setTxtFile}
            onUploadTxt={uploadTxt}
            canRun={canRun}
            ingestedChapterCount={ingestedChapterCount}
          />
        </Suspense>

        <Suspense fallback={<SectionFallback />}>
          <ModeSelectionSection
            loading={isBusy}
            canSelectMode={canSelectMode}
            modeOptions={modeOptions}
            selectedMode={selectedMode}
            onSelectedModeChange={setSelectedMode}
            modeCatalog={modeCatalog}
            projectMode={project?.selected_mode ?? null}
            runMode={runModeFromConfig}
          />
        </Suspense>

        <Suspense fallback={<SectionFallback />}>
          <CharacterImportSection
            loading={isBusy}
            canRun={canRun}
            characterFile={charFile}
            onCharacterFileChange={setCharFile}
            onUploadCharacters={uploadCharacters}
            importedCount={importedCount}
          />
        </Suspense>

        <Suspense fallback={<SectionFallback />}>
          <RunConfigurationSection
            loading={isBusy}
            canRun={canRun}
            narratorVoice={narratorVoice}
            maleVoice={maleVoice}
            femaleVoice={femaleVoice}
            maxSegmentChars={maxSegmentChars}
            llmEnabled={llmEnabled}
            providerName={providerName}
            maxCallsPerDay={maxCallsPerDay}
            onNarratorVoiceChange={setNarratorVoice}
            onMaleVoiceChange={setMaleVoice}
            onFemaleVoiceChange={setFemaleVoice}
            onMaxSegmentCharsChange={setMaxSegmentChars}
            onLlmEnabledChange={setLlmEnabled}
            onProviderNameChange={setProviderName}
            onMaxCallsPerDayChange={setMaxCallsPerDay}
            onSaveVoices={saveVoices}
            onRunPipeline={runPipeline}
          />
        </Suspense>

        <Suspense fallback={<SectionFallback />}>
          <RunArtifactsSection
            loading={isBusy}
            projectId={project?.id ?? null}
            runId={runId}
            runDetail={runDetail}
            exportPayload={exportPayload}
            onRefreshRun={refreshCurrentRun}
          />
        </Suspense>
      </div>

      <ToastStack />
    </div>
  );
}

export default ControlDeckPage;
