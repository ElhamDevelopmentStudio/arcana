import { type FormEvent, useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import { Upload, X, FileText, BookOpen, GraduationCap, Pen, Sliders } from 'lucide-react';

import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import {
  useCreateProjectDraftMutation,
  useIngestTxtMutation,
  useIngestMarkdownMutation,
  useIngestEpubMutation,
  useSwitchModeMutation,
} from '@/features/workflow/api/workflow-hooks';

type WizardStep = 1 | 2 | 3;
type IngestionSource = 'txt' | 'markdown' | 'epub';

const MODES = [
  { id: 'audiobook', label: 'Audiobook', description: 'Optimized for novels and narrative fiction', icon: BookOpen },
  { id: 'academic', label: 'Academic', description: 'Structured for papers and scholarly texts', icon: GraduationCap },
  { id: 'author', label: 'Author', description: 'Balanced processing for authored content', icon: Pen },
  { id: 'custom', label: 'Custom', description: 'Manual configuration of all pipeline parameters', icon: Sliders },
] as const;

const SOURCE_TABS: { id: IngestionSource; label: string; accept: string }[] = [
  { id: 'txt', label: 'TXT', accept: '.txt' },
  { id: 'markdown', label: 'Markdown', accept: '.md,.markdown' },
  { id: 'epub', label: 'EPUB', accept: '.epub' },
];

export function ProjectNewPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<WizardStep>(1);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [ingestionSource, setIngestionSource] = useState<IngestionSource>('txt');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedMode, setSelectedMode] = useState<string>('audiobook');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const projectId = useWorkspaceStore((state) => state.projectId);
  const setProject = useWorkspaceStore((state) => state.setProject);
  const setChapterCount = useWorkspaceStore((state) => state.setChapterCount);

  const createDraftMutation = useCreateProjectDraftMutation();
  const ingestTxtMutation = useIngestTxtMutation(projectId);
  const ingestMarkdownMutation = useIngestMarkdownMutation(projectId);
  const ingestEpubMutation = useIngestEpubMutation(projectId);
  const switchModeMutation = useSwitchModeMutation(projectId);

  const isBusy =
    createDraftMutation.isMutating ||
    ingestTxtMutation.isMutating ||
    ingestMarkdownMutation.isMutating ||
    ingestEpubMutation.isMutating ||
    switchModeMutation.isMutating;

  async function handleStep1(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) { toast.error('Project name is required.'); return; }
    try {
      const project = await createDraftMutation.trigger({ title: title.trim(), do_not_store_source_text: false });
      setProject({ projectId: project.id, projectTitle: project.title, selectedMode: null });
      setStep(2);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create project');
    }
  }

  async function handleStep2(e: FormEvent) {
    e.preventDefault();
    if (!selectedFile) { toast.error('Please select a file to upload.'); return; }
    if (projectId === null) { toast.error('Project not created yet.'); return; }
    try {
      let response;
      if (ingestionSource === 'txt') response = await ingestTxtMutation.trigger({ file: selectedFile });
      else if (ingestionSource === 'markdown') response = await ingestMarkdownMutation.trigger({ file: selectedFile });
      else response = await ingestEpubMutation.trigger({ file: selectedFile });
      setChapterCount(response.chapter_count);
      toast.success(`Ingested ${response.chapter_count} chapters.`);
      setStep(3);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Ingestion failed');
    }
  }

  async function handleStep3(e: FormEvent) {
    e.preventDefault();
    if (projectId === null) { toast.error('Project not found.'); return; }
    try {
      await switchModeMutation.trigger({ mode: selectedMode });
      toast.success('Project created successfully.');
      navigate(`/projects/${projectId}/overview`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to set mode');
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) setSelectedFile(file);
  }

  return (
    <div className="flex h-full flex-col overflow-auto bg-background">
      {/* Close button */}
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-white/10 px-6">
        <Link className="text-sm font-semibold text-foreground" to="/dashboard">nipe</Link>
        <Link
          aria-label="Cancel and go to dashboard"
          className="grid size-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground"
          to="/dashboard"
        >
          <X size={16} />
        </Link>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center px-4 py-12">
        <div className="w-full max-w-lg">
          {/* Step indicator */}
          <div className="mb-10 flex items-center justify-center gap-2">
            {([1, 2, 3] as const).map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                <div className={cn(
                  'flex size-7 items-center justify-center rounded-full text-xs font-medium transition-colors',
                  step === s ? 'bg-foreground text-background' :
                  step > s ? 'bg-white/20 text-foreground' : 'bg-white/5 text-muted-foreground',
                )}>
                  {step > s ? '✓' : s}
                </div>
                <span className={cn('hidden text-xs sm:inline', step === s ? 'text-foreground' : 'text-muted-foreground')}>
                  {s === 1 ? 'Name' : s === 2 ? 'Upload' : 'Mode'}
                </span>
                {i < 2 && <div className="h-px w-8 bg-white/10" />}
              </div>
            ))}
          </div>

          {/* Step 1: Name */}
          {step === 1 && (
            <form onSubmit={handleStep1} className="animate-fade-in-up space-y-6">
              <div>
                <h1 className="text-2xl font-bold text-foreground">Name your project</h1>
                <p className="mt-1 text-sm text-muted-foreground">Give your project a descriptive name. You can change this later.</p>
              </div>
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-foreground" htmlFor="project-title">Project name</label>
                  <Input
                    autoFocus
                    data-testid="project-title-input"
                    id="project-title"
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g., Shadow Slave Vol. 1"
                    required
                    value={title}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-foreground" htmlFor="project-desc">Description <span className="text-muted-foreground">(optional)</span></label>
                  <textarea
                    className="w-full resize-none rounded-md border border-white/15 bg-white/5 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60 outline-none transition-[border-color] focus:border-white/30"
                    id="project-desc"
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Brief description of the source material"
                    rows={3}
                    value={description}
                  />
                </div>
              </div>
              <Button className="w-full" disabled={isBusy} type="submit">
                {createDraftMutation.isMutating ? 'Creating…' : 'Continue'}
              </Button>
            </form>
          )}

          {/* Step 2: Upload */}
          {step === 2 && (
            <form onSubmit={handleStep2} className="animate-fade-in-up space-y-6">
              <div>
                <h1 className="text-2xl font-bold text-foreground">Add your source text</h1>
                <p className="mt-1 text-sm text-muted-foreground">Upload a file or switch between supported formats.</p>
              </div>

              {/* Format tabs */}
              <div className="flex gap-1 rounded-lg border border-white/10 bg-card p-1">
                {SOURCE_TABS.map((tab) => (
                  <button
                    className={cn(
                      'flex-1 rounded-md py-1.5 text-sm transition-colors',
                      ingestionSource === tab.id ? 'bg-white/10 text-foreground' : 'text-muted-foreground hover:text-foreground',
                    )}
                    key={tab.id}
                    onClick={() => { setIngestionSource(tab.id); setSelectedFile(null); }}
                    type="button"
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Drop zone */}
              <div
                className={cn(
                  'flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-12 text-center transition-colors',
                  isDragging ? 'border-white/40 bg-white/5' : 'border-white/15 hover:border-white/25',
                )}
                onClick={() => fileInputRef.current?.click()}
                onDragLeave={() => setIsDragging(false)}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDrop={handleDrop}
              >
                {selectedFile ? (
                  <>
                    <FileText className="text-muted-foreground" size={28} />
                    <p className="text-sm font-medium text-foreground">{selectedFile.name}</p>
                    <p className="text-xs text-muted-foreground">{(selectedFile.size / 1024).toFixed(0)} KB</p>
                    <button
                      className="text-xs text-muted-foreground underline hover:text-foreground"
                      onClick={(e) => { e.stopPropagation(); setSelectedFile(null); }}
                      type="button"
                    >
                      Remove file
                    </button>
                  </>
                ) : (
                  <>
                    <Upload className="text-muted-foreground" size={28} />
                    <div>
                      <p className="text-sm font-medium text-foreground">Drop your file here, or click to browse</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {SOURCE_TABS.find((t) => t.id === ingestionSource)?.accept ?? '.txt'} up to 50 MB
                      </p>
                    </div>
                  </>
                )}
              </div>
              <input
                accept={SOURCE_TABS.find((t) => t.id === ingestionSource)?.accept}
                className="hidden"
                data-testid="txt-upload-input"
                onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
                ref={fileInputRef}
                type="file"
              />

              <div className="flex gap-3">
                <Button
                  className="flex-1"
                  onClick={() => setStep(1)}
                  type="button"
                  variant="outline"
                >
                  Back
                </Button>
                <Button className="flex-1" data-testid="upload-txt-button" disabled={isBusy || !selectedFile} type="submit">
                  {isBusy ? 'Uploading…' : 'Continue'}
                </Button>
              </div>
            </form>
          )}

          {/* Step 3: Mode */}
          {step === 3 && (
            <form onSubmit={handleStep3} className="animate-fade-in-up space-y-6">
              <div>
                <h1 className="text-2xl font-bold text-foreground">Choose a processing mode</h1>
                <p className="mt-1 text-sm text-muted-foreground">Each mode optimizes the pipeline for a specific type of content.</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {MODES.map((mode) => {
                  const Icon = mode.icon;
                  return (
                    <button
                      className={cn(
                        'flex flex-col gap-2 rounded-xl border p-4 text-left transition-all',
                        selectedMode === mode.id
                          ? 'border-white/50 bg-white/5'
                          : 'border-white/10 hover:border-white/20',
                      )}
                      data-testid={`mode-card-${mode.id}`}
                      key={mode.id}
                      onClick={() => setSelectedMode(mode.id)}
                      type="button"
                    >
                      <Icon className="text-muted-foreground" size={18} />
                      <p className="text-sm font-semibold text-foreground">{mode.label}</p>
                      <p className="text-xs text-muted-foreground">{mode.description}</p>
                    </button>
                  );
                })}
              </div>

              <div className="flex gap-3">
                <Button className="flex-1" onClick={() => setStep(2)} type="button" variant="outline">Back</Button>
                <Button className="flex-1" data-testid="create-project-button" disabled={isBusy} type="submit">
                  {switchModeMutation.isMutating ? 'Creating…' : 'Create Project'}
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
