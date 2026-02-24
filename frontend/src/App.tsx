import { FormEvent, useMemo, useState } from "react";

type RunDetail = {
  run_id: number;
  project_id: number;
  status: string;
  config: Record<string, unknown>;
  started_at: string;
  finished_at: string | null;
  segment_count: number;
  llm_calls: Array<{
    id: number;
    provider: string;
    task_type: string;
    success: boolean;
    request_count: number;
    detail: string | null;
    created_at: string;
  }>;
};

type ExportPayload = {
  project_id: number;
  project_title: string;
  run_id: number;
  status: string;
  segments: Array<Record<string, unknown>>;
};

type ModeCatalog = {
  modes: string[];
  default_mode: string;
  persisted_in: string[];
};

const FALLBACK_MODES = ["audiobook", "academic", "author", "custom"] as const;

export function resolveModeOptions(catalog: ModeCatalog | null): string[] {
  if (!catalog || !Array.isArray(catalog.modes) || catalog.modes.length === 0) {
    return [...FALLBACK_MODES];
  }
  return catalog.modes;
}

export function pickModeFromCatalog(catalog: ModeCatalog, preferredMode?: string): string {
  const options = resolveModeOptions(catalog);
  if (preferredMode && options.includes(preferredMode)) {
    return preferredMode;
  }
  if (catalog.default_mode && options.includes(catalog.default_mode)) {
    return catalog.default_mode;
  }
  return options[0];
}

function App() {
  const [apiBase, setApiBase] = useState(import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000");
  const [projectTitle, setProjectTitle] = useState("Shadow Slave PoC");
  const [projectId, setProjectId] = useState<number | null>(null);
  const [ingestedChapterCount, setIngestedChapterCount] = useState<number | null>(null);
  const [runId, setRunId] = useState<number | null>(null);
  const [txtFile, setTxtFile] = useState<File | null>(null);
  const [charFile, setCharFile] = useState<File | null>(null);
  const [modeCatalog, setModeCatalog] = useState<ModeCatalog | null>(null);
  const [selectedMode, setSelectedMode] = useState<string>(FALLBACK_MODES[0]);

  const [narratorVoice, setNarratorVoice] = useState("narrator_default");
  const [maleVoice, setMaleVoice] = useState("male_default");
  const [femaleVoice, setFemaleVoice] = useState("female_default");

  const [maxSegmentChars, setMaxSegmentChars] = useState(255);
  const [llmEnabled, setLlmEnabled] = useState(false);
  const [providerName, setProviderName] = useState("openrouter");
  const [maxCallsPerDay, setMaxCallsPerDay] = useState(25);

  const [runDetail, setRunDetail] = useState<RunDetail | null>(null);
  const [exportPayload, setExportPayload] = useState<ExportPayload | null>(null);
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const canRun = useMemo(() => projectId !== null, [projectId]);
  const canSelectMode = useMemo(
    () => projectId !== null && ingestedChapterCount !== null,
    [projectId, ingestedChapterCount]
  );
  const modeOptions = useMemo(() => resolveModeOptions(modeCatalog), [modeCatalog]);

  async function request(path: string, init?: RequestInit) {
    const response = await fetch(`${apiBase}${path}`, init);
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return response;
  }

  async function loadModeCatalog(preferredMode?: string) {
    const response = await request("/api/modes");
    const data = (await response.json()) as ModeCatalog;
    setModeCatalog(data);
    setSelectedMode(pickModeFromCatalog(data, preferredMode));
  }

  async function createProject(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);
    try {
      const response = await request("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: projectTitle })
      });
      const data = await response.json();
      setProjectId(data.id);
      setIngestedChapterCount(null);
      setRunId(null);
      setRunDetail(null);
      setExportPayload(null);
      setMessage(`Project created: ${data.id}`);
      try {
        await loadModeCatalog(data.selected_mode);
      } catch {
        setError("Project created, but failed to load available modes.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setLoading(false);
    }
  }

  async function uploadTxt(e: FormEvent) {
    e.preventDefault();
    if (!projectId || !txtFile) {
      return;
    }

    setError("");
    setMessage("");
    setLoading(true);

    try {
      const form = new FormData();
      form.append("file", txtFile);
      const response = await request(`/api/projects/${projectId}/ingest/txt`, {
        method: "POST",
        body: form
      });
      const data = await response.json();
      setIngestedChapterCount(data.chapter_count);
      if (!modeCatalog) {
        try {
          await loadModeCatalog(selectedMode);
        } catch {
          setError("TXT ingested, but failed to load available modes.");
        }
      }
      setMessage(`TXT ingested. Chapters detected: ${data.chapter_count}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to ingest TXT");
    } finally {
      setLoading(false);
    }
  }

  async function uploadCharacters(e: FormEvent) {
    e.preventDefault();
    if (!projectId || !charFile) {
      return;
    }

    setError("");
    setMessage("");
    setLoading(true);

    try {
      const form = new FormData();
      form.append("file", charFile);
      const response = await request(`/api/projects/${projectId}/characters/import`, {
        method: "POST",
        body: form
      });
      const data = await response.json();
      setMessage(`Characters imported: ${data.imported_count}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import character map");
    } finally {
      setLoading(false);
    }
  }

  async function saveVoices(e: FormEvent) {
    e.preventDefault();
    if (!projectId) {
      return;
    }

    setError("");
    setMessage("");
    setLoading(true);

    try {
      await request(`/api/projects/${projectId}/voices`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          narrator_voice: narratorVoice,
          male_default_voice: maleVoice,
          female_default_voice: femaleVoice
        })
      });
      setMessage("Voice config saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save voice config");
    } finally {
      setLoading(false);
    }
  }

  async function runPipeline(e: FormEvent) {
    e.preventDefault();
    if (!projectId) {
      return;
    }

    setError("");
    setMessage("");
    setLoading(true);

    try {
      const response = await request(`/api/projects/${projectId}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: selectedMode,
          max_segment_chars: maxSegmentChars,
          llm_enabled: llmEnabled,
          provider_name: providerName,
          max_calls_per_day: maxCallsPerDay
        })
      });

      const data = await response.json();
      setRunId(data.run_id);
      setMessage(`Pipeline finished. Segments: ${data.segment_count}`);
      await refreshRunArtifacts(projectId, data.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run failed");
    } finally {
      setLoading(false);
    }
  }

  async function refreshRunArtifacts(currentProjectId: number, currentRunId: number) {
    const [runResponse, exportResponse] = await Promise.all([
      request(`/api/projects/${currentProjectId}/runs/${currentRunId}`),
      request(`/api/projects/${currentProjectId}/exports/${currentRunId}.json`)
    ]);

    setRunDetail(await runResponse.json());
    setExportPayload(await exportResponse.json());
  }

  async function refreshCurrentRun() {
    if (!projectId || !runId) {
      return;
    }

    setError("");
    setMessage("");
    setLoading(true);

    try {
      await refreshRunArtifacts(projectId, runId);
      setMessage("Run detail and export refreshed");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh run artifacts");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header>
        <h1>NIPE PoC Controller</h1>
        <p>PoC-only workflow: ingest, map, run, export.</p>
      </header>

      <section className="card">
        <h2>Connection</h2>
        <label>
          API Base URL
          <input value={apiBase} onChange={(e) => setApiBase(e.target.value)} />
        </label>
      </section>

      <section className="card">
        <h2>1) Project Setup + TXT Upload</h2>
        <form onSubmit={createProject} className="form-row">
          <input
            value={projectTitle}
            onChange={(e) => setProjectTitle(e.target.value)}
            placeholder="Project title"
          />
          <button disabled={loading} type="submit">Create Project</button>
        </form>
        <p>Project ID: {projectId ?? "not created"}</p>

        <form onSubmit={uploadTxt} className="form-row">
          <input type="file" accept=".txt" onChange={(e) => setTxtFile(e.target.files?.[0] ?? null)} />
          <button disabled={loading || !canRun || !txtFile} type="submit">Upload TXT</button>
        </form>
      </section>

      <section className="card">
        <h2>2) Mode Selection (Post-Ingestion)</h2>
        <label>
          Processing mode
          <select
            data-testid="mode-select"
            value={selectedMode}
            disabled={loading || !canSelectMode}
            onChange={(e) => setSelectedMode(e.target.value)}
          >
            {modeOptions.map((mode) => (
              <option key={mode} value={mode}>
                {mode}
              </option>
            ))}
          </select>
        </label>
        {!canSelectMode ? (
          <p>Upload TXT first to unlock mode selection.</p>
        ) : (
          <p>Selected mode will be included in the run configuration snapshot.</p>
        )}
        {modeCatalog ? <p>Mode persistence: {modeCatalog.persisted_in.join(" | ")}</p> : null}
      </section>

      <section className="card">
        <h2>3) Character Map Upload</h2>
        <form onSubmit={uploadCharacters} className="form-row">
          <input
            type="file"
            accept=".json,.csv"
            onChange={(e) => setCharFile(e.target.files?.[0] ?? null)}
          />
          <button disabled={loading || !canRun || !charFile} type="submit">Import Character Map</button>
        </form>
      </section>

      <section className="card">
        <h2>4) Voice Config + Run Pipeline</h2>
        <form onSubmit={saveVoices} className="grid-form">
          <label>
            Narrator voice
            <input value={narratorVoice} onChange={(e) => setNarratorVoice(e.target.value)} />
          </label>
          <label>
            Male default voice
            <input value={maleVoice} onChange={(e) => setMaleVoice(e.target.value)} />
          </label>
          <label>
            Female default voice
            <input value={femaleVoice} onChange={(e) => setFemaleVoice(e.target.value)} />
          </label>
          <button disabled={loading || !canRun} type="submit">Save Voices</button>
        </form>

        <form onSubmit={runPipeline} className="grid-form">
          <label>
            Max segment chars
            <input
              type="number"
              min={80}
              max={255}
              value={maxSegmentChars}
              onChange={(e) => setMaxSegmentChars(Number(e.target.value))}
            />
          </label>
          <label>
            LLM enabled
            <input type="checkbox" checked={llmEnabled} onChange={(e) => setLlmEnabled(e.target.checked)} />
          </label>
          <label>
            Provider name
            <input value={providerName} onChange={(e) => setProviderName(e.target.value)} />
          </label>
          <label>
            Max calls/day
            <input
              type="number"
              min={1}
              value={maxCallsPerDay}
              onChange={(e) => setMaxCallsPerDay(Number(e.target.value))}
            />
          </label>
          <button disabled={loading || !canRun} type="submit">Run Pipeline</button>
        </form>
      </section>

      <section className="card">
        <h2>5) Export + Logs</h2>
        <p>Run ID: {runId ?? "none"}</p>
        <button disabled={loading || !projectId || !runId} onClick={refreshCurrentRun} type="button">
          Refresh Run Artifacts
        </button>

        {runDetail && (
          <div className="panel">
            <h3>Run Status</h3>
            <pre>{JSON.stringify(runDetail, null, 2)}</pre>
          </div>
        )}

        {exportPayload && (
          <div className="panel">
            <h3>Export JSON</h3>
            <pre>{JSON.stringify(exportPayload, null, 2)}</pre>
          </div>
        )}
      </section>

      {message ? <p className="msg ok">{message}</p> : null}
      {error ? <p className="msg err">{error}</p> : null}
    </div>
  );
}

export default App;
