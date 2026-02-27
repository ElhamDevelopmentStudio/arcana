import { type FormEvent, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Upload, FileText, CheckCircle2 } from 'lucide-react';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import {
  useProjectIngestionJobStatusQuery,
  useStartProjectIngestionJobMutation,
  useProjectSetupStatusQuery,
} from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import { cn } from '@/lib/utils';
import { useJobNotificationStore } from '@/features/workflow/state/job-notification-store';

type IngestionSource = 'txt' | 'markdown' | 'epub' | 'directory';

const SOURCE_TABS: { id: IngestionSource; label: string; accept: string; multiple?: boolean }[] = [
  { id: 'txt', label: 'TXT', accept: '.txt' },
  { id: 'markdown', label: 'Markdown', accept: '.md,.markdown' },
  { id: 'epub', label: 'EPUB', accept: '.epub' },
  { id: 'directory', label: 'Chapter Directory', accept: '.txt', multiple: true },
];

export function ProjectSetupPage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const chapterCount = useWorkspaceStore((state) => state.chapterCount);
  const setChapterCount = useWorkspaceStore((state) => state.setChapterCount);
  const projectId = routeProjectId ?? storeProjectId;

  const [source, setSource] = useState<IngestionSource>('txt');
  const [file, setFile] = useState<File | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [appendFile, setAppendFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [activeIngestionJobId, setActiveIngestionJobId] = useState<string | null>(null);
  const [activeIngestionSource, setActiveIngestionSource] = useState<
    'txt' | 'markdown' | 'epub' | 'chapters-dir' | 'append-chapter' | null
  >(null);
  const ingestionCompletionJobRef = useRef<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const registerJob = useJobNotificationStore((state) => state.registerJob);

  const setupStatusQuery = useProjectSetupStatusQuery(projectId);
  const startIngestionJobMutation = useStartProjectIngestionJobMutation(projectId);
  const ingestionJobStatus = useProjectIngestionJobStatusQuery(projectId, activeIngestionJobId).data;
  const ingestionJobIsActive = ingestionJobStatus?.status === 'queued' || ingestionJobStatus?.status === 'running';
  const ingestionProgress = ingestionJobStatus?.progress ?? 0;

  const ingestionReady = setupStatusQuery.data?.steps?.some((s) => s.step_id === 'ingestion' && s.ready) ?? false;
  const isBusy = startIngestionJobMutation.isMutating || ingestionJobIsActive;

  useEffect(() => {
    if (!activeIngestionJobId || !ingestionJobStatus) {
      return;
    }
    if (ingestionCompletionJobRef.current === activeIngestionJobId) {
      return;
    }

    if (ingestionJobStatus.status === 'completed') {
      ingestionCompletionJobRef.current = activeIngestionJobId;
      const result = ingestionJobStatus.result;
      queueMicrotask(() => {
        setActiveIngestionJobId(null);
        setActiveIngestionSource(null);
      });

      if (result) {
        setChapterCount(result.chapter_count);
      }

      if (activeIngestionSource === 'append-chapter') {
        queueMicrotask(() => {
          setAppendFile(null);
        });
        toast.success(result ? `Chapter appended. Total: ${result.chapter_count}.` : 'Chapter appended.');
      } else {
        queueMicrotask(() => {
          setFile(null);
          setFiles([]);
        });
        toast.success(result ? `Ingested ${result.chapter_count} chapters.` : 'Ingestion completed.');
      }
      void setupStatusQuery.mutate();
      return;
    }

    if (ingestionJobStatus.status === 'failed') {
      ingestionCompletionJobRef.current = activeIngestionJobId;
      queueMicrotask(() => {
        setActiveIngestionJobId(null);
        setActiveIngestionSource(null);
      });
      toast.error(ingestionJobStatus.error_message || 'Ingestion failed');
    }
  }, [
    activeIngestionJobId,
    activeIngestionSource,
    ingestionJobStatus,
    setChapterCount,
    setupStatusQuery,
  ]);

  const tab = SOURCE_TABS.find((t) => t.id === source)!;

  async function handleIngest(e: FormEvent) {
    e.preventDefault();
    if (projectId === null) { toast.error('No project found.'); return; }
    try {
      let payload: { source: 'txt' | 'markdown' | 'epub' | 'chapters-dir'; file?: File; files?: File[] } | null = null;
      if (source === 'txt' && file) payload = { source: 'txt', file };
      else if (source === 'markdown' && file) payload = { source: 'markdown', file };
      else if (source === 'epub' && file) payload = { source: 'epub', file };
      else if (source === 'directory' && files.length) payload = { source: 'chapters-dir', files };
      else { toast.error('Select a file first.'); return; }

      const job = await startIngestionJobMutation.trigger(payload);
      ingestionCompletionJobRef.current = null;
      setActiveIngestionSource(payload.source);
      setActiveIngestionJobId(job.job_id);
      registerJob({
        type: 'ingestion',
        projectId,
        jobId: job.job_id,
        status: job.status,
      });
      toast.success('Ingestion started.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Ingestion failed');
    }
  }

  async function handleAppend() {
    if (!appendFile || projectId === null) { toast.error('Select a chapter file.'); return; }
    try {
      const job = await startIngestionJobMutation.trigger({
        source: 'append-chapter',
        file: appendFile,
      });
      ingestionCompletionJobRef.current = null;
      setActiveIngestionSource('append-chapter');
      setActiveIngestionJobId(job.job_id);
      registerJob({
        type: 'ingestion',
        projectId,
        jobId: job.job_id,
        status: job.status,
      });
      toast.success('Append chapter started.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Append failed');
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    if (source === 'directory') setFiles(Array.from(e.dataTransfer.files));
    else setFile(e.dataTransfer.files[0] ?? null);
  }

  const activeFile = source === 'directory' ? null : file;
  const activeFiles = source === 'directory' ? files : [];

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Upload`}
      title="Upload Source"
      description="Ingest your source text to begin processing."
      action={
        ingestionReady && projectId !== null ? (
          <Button
            data-testid="setup-continue-to-mode"
            onClick={() => navigate(`/projects/${projectId}/mode`)}
          >
            Continue to Mode
          </Button>
        ) : undefined
      }
    >
      {ingestionReady && (
        <div className="flex items-center gap-2 rounded-xl border border-green-400/20 bg-green-400/5 px-4 py-3 text-sm text-green-400">
          <CheckCircle2 size={16} />
          Source ingested — {chapterCount ?? 'chapters'} detected. You can re-ingest or continue to Mode.
        </div>
      )}

      <form className="max-w-xl space-y-5" data-testid="project-setup-form" onSubmit={handleIngest}>
        {/* Source type tabs */}
        <div className="flex gap-1 rounded-lg border border-white/10 bg-card p-1">
          {SOURCE_TABS.map((tab) => (
            <button
              className={cn(
                'flex-1 rounded-md py-1.5 text-xs transition-colors',
                source === tab.id ? 'bg-white/10 text-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
              key={tab.id}
              onClick={() => { setSource(tab.id); setFile(null); setFiles([]); }}
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Drop zone */}
        <div
          className={cn(
            'flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-10 text-center transition-colors',
            isDragging ? 'border-white/40 bg-white/5' : 'border-white/15 hover:border-white/25',
          )}
          onClick={() => fileInputRef.current?.click()}
          onDragLeave={() => setIsDragging(false)}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDrop={handleDrop}
        >
          {activeFile ? (
            <>
              <FileText className="text-muted-foreground" size={28} />
              <p className="text-sm font-medium text-foreground">{activeFile.name}</p>
              <p className="text-xs text-muted-foreground">{(activeFile.size / 1024).toFixed(0)} KB</p>
            </>
          ) : activeFiles.length > 0 ? (
            <>
              <FileText className="text-muted-foreground" size={28} />
              <p className="text-sm font-medium text-foreground">{activeFiles.length} files selected</p>
            </>
          ) : (
            <>
              <Upload className="text-muted-foreground" size={28} />
              <p className="text-sm font-medium text-foreground">Drop your file here, or click to browse</p>
              <p className="text-xs text-muted-foreground">{tab.accept}</p>
            </>
          )}
        </div>
        <input
          accept={tab.accept}
          className="hidden"
          data-testid={source === 'directory' ? 'directory-upload-input' : 'txt-upload-input'}
          multiple={tab.multiple}
          onChange={(e) => {
            if (source === 'directory') setFiles(Array.from(e.target.files ?? []));
            else setFile(e.target.files?.[0] ?? null);
          }}
          ref={fileInputRef}
          type="file"
        />

        <Button
          className="w-full"
          data-testid="upload-txt-button"
          disabled={isBusy || (source === 'directory' ? files.length === 0 : !file)}
          type="submit"
        >
          {isBusy ? 'Processing…' : 'Upload & Parse'}
        </Button>
        {ingestionJobIsActive && (
          <p className="text-center text-xs text-muted-foreground">
            Ingestion progress: {ingestionProgress}%
          </p>
        )}
      </form>

      {/* Append chapter */}
      {ingestionReady && (
        <div className="max-w-xl rounded-xl border border-white/10 bg-card p-5">
          <p className="mb-1 text-sm font-medium text-foreground">Append one chapter</p>
          <p className="mb-3 text-xs text-muted-foreground">Add a single .txt chapter to an already-ingested project.</p>
          <div className="flex gap-2">
            <input
              accept=".txt"
              className="hidden"
              data-testid="append-chapter-upload-input"
              id="append-chapter-file"
              onChange={(e) => setAppendFile(e.target.files?.[0] ?? null)}
              type="file"
            />
            <label
              className={cn(
                'inline-flex h-9 cursor-pointer items-center rounded-md border border-white/15 bg-transparent px-3 text-xs text-muted-foreground transition-colors hover:border-white/25 hover:text-foreground',
                isBusy && 'pointer-events-none opacity-40',
              )}
              htmlFor="append-chapter-file"
            >
              {appendFile ? appendFile.name : 'Choose .txt file'}
            </label>
            <Button
              data-testid="append-chapter-button"
              disabled={isBusy || !appendFile}
              onClick={() => void handleAppend()}
              size="sm"
              variant="outline"
            >
              {isBusy && activeIngestionSource === 'append-chapter' ? 'Appending…' : 'Append Chapter'}
            </Button>
          </div>
        </div>
      )}
    </WorkflowPageShell>
  );
}
