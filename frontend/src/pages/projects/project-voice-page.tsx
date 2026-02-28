import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import { WorkflowPageShell } from '@/app/workflow-page-shell';
import { useWorkspaceStore } from '@/app/state/workspace-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useSaveVoicesMutation } from '@/features/workflow/api/workflow-hooks';
import { parseProjectIdParam } from '@/features/workflow/utils/project-route';
import type { VoiceConfigDto } from '@/app/schemas/api';
import { cn } from '@/lib/utils';

const VOICE_FIELDS: { key: keyof VoiceConfigDto; label: string; description: string }[] = [
  { key: 'narrator_voice', label: 'Narrator Voice', description: 'Voice ID used for all narrator and unattributed passages' },
  { key: 'male_default_voice', label: 'Male Default', description: 'Fallback voice for characters with male gender assignment' },
  { key: 'female_default_voice', label: 'Female Default', description: 'Fallback voice for characters with female gender assignment' },
  { key: 'neutral_default_voice', label: 'Neutral Default', description: 'Fallback voice for characters with neutral gender assignment' },
  { key: 'unknown_default_voice', label: 'Unknown Default', description: 'Fallback voice for characters with unresolved gender' },
];

const THOUGHT_POLICIES = [
  { value: 'character', label: 'Character', description: 'Internal thoughts spoken in character\'s own voice' },
  { value: 'narrator', label: 'Narrator', description: 'Internal thoughts spoken by the narrator voice' },
  { value: 'thought_voice', label: 'Custom Thought Voice', description: 'Internal thoughts use a dedicated custom voice' },
] as const;

type ThoughtPolicy = 'character' | 'narrator' | 'thought_voice';

function SettingRow({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-6 border-b border-white/5 py-4 last:border-0">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{label}</p>
        {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
      </div>
      <div className="shrink-0 w-64">{children}</div>
    </div>
  );
}

export function ProjectVoicePage() {
  const navigate = useNavigate();
  const params = useParams<{ project_id: string }>();
  const routeProjectId = parseProjectIdParam(params.project_id);
  const storeProjectId = useWorkspaceStore((state) => state.projectId);
  const projectId = routeProjectId ?? storeProjectId;

  const [voices, setVoices] = useState<Record<string, string>>({
    narrator_voice: '',
    male_default_voice: '',
    female_default_voice: '',
    neutral_default_voice: '',
    unknown_default_voice: '',
    internal_thought_voice: '',
  });
  const [thoughtPolicy, setThoughtPolicy] = useState<ThoughtPolicy>('character');

  const saveVoicesMutation = useSaveVoicesMutation(projectId);

  function setVoice(key: string, value: string) {
    setVoices((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    const required = VOICE_FIELDS.map((f) => voices[f.key]).every((v) => v.trim());
    if (!required) {
      toast.error('All default voice fields are required.');
      return;
    }
    try {
      const payload: VoiceConfigDto = {
        narrator_voice: voices.narrator_voice.trim(),
        male_default_voice: voices.male_default_voice.trim(),
        female_default_voice: voices.female_default_voice.trim(),
        neutral_default_voice: voices.neutral_default_voice.trim(),
        unknown_default_voice: voices.unknown_default_voice.trim(),
        internal_thought_voice_policy: thoughtPolicy,
        internal_thought_voice: thoughtPolicy === 'thought_voice' ? voices.internal_thought_voice.trim() || undefined : undefined,
      };
      await saveVoicesMutation.trigger(payload);
      toast.success('Voice configuration saved.');
      if (projectId !== null) navigate(`/projects/${projectId}/pipeline-setup`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save voices');
    }
  }

  return (
    <WorkflowPageShell
      breadcrumb={`All Projects › Project #${projectId ?? '—'} › Voice`}
      title="Voice Assignment"
      description="Configure default voice IDs for each character gender role and narrator. Voice IDs correspond to your TTS provider's voice identifiers."
    >
      <div className="max-w-2xl space-y-2">
        {/* Default voices */}
        <div className="rounded-xl border border-white/10 bg-card px-5">
          <p className="pt-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">Default Voice Assignments</p>
          {VOICE_FIELDS.map((field) => (
            <SettingRow key={field.key} label={field.label} description={field.description}>
              <Input
                data-testid={`voice-input-${field.key}`}
                onChange={(e) => setVoice(field.key, e.target.value)}
                placeholder="e.g. voice_abc123"
                value={voices[field.key]}
              />
            </SettingRow>
          ))}
        </div>

        {/* Internal thought policy */}
        <div className="rounded-xl border border-white/10 bg-card px-5">
          <p className="pt-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">Internal Thought Policy</p>
          <div className="py-4 space-y-2">
            {THOUGHT_POLICIES.map((policy) => (
              <button
                className={cn(
                  'flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors',
                  thoughtPolicy === policy.value
                    ? 'border-white/40 bg-white/5'
                    : 'border-white/10 hover:border-white/20',
                )}
                key={policy.value}
                onClick={() => setThoughtPolicy(policy.value)}
                type="button"
              >
                <span className={cn(
                  'mt-0.5 size-4 shrink-0 rounded-full border-2 transition-colors',
                  thoughtPolicy === policy.value ? 'border-foreground bg-foreground' : 'border-white/30',
                )} />
                <div>
                  <p className="text-sm font-medium text-foreground">{policy.label}</p>
                  <p className="text-xs text-muted-foreground">{policy.description}</p>
                </div>
              </button>
            ))}
          </div>

          {thoughtPolicy === 'thought_voice' && (
            <SettingRow label="Custom Thought Voice ID" description="Voice ID to use for internal monologue passages">
              <Input
                data-testid="voice-input-internal-thought"
                onChange={(e) => setVoice('internal_thought_voice', e.target.value)}
                placeholder="e.g. voice_thought123"
                value={voices.internal_thought_voice}
              />
            </SettingRow>
          )}
        </div>

        {/* Info */}
        <div className="rounded-xl border border-white/10 bg-card px-5 py-4">
          <p className="text-xs text-muted-foreground leading-relaxed">
            Voice IDs are strings provided by your TTS provider (e.g. ElevenLabs, OpenAI). 
            These defaults apply to any character that doesn't have a specific voice override configured. 
            After saving, proceed to <strong className="text-foreground">Pipeline Setup</strong> to trigger a run.
          </p>
        </div>

        <div className="flex gap-3 pt-2">
          <Button
            data-testid="save-voices-button"
            disabled={saveVoicesMutation.isMutating}
            onClick={() => void handleSave()}
          >
            {saveVoicesMutation.isMutating ? 'Saving…' : 'Save Voice Configuration'}
          </Button>
        </div>
      </div>
    </WorkflowPageShell>
  );
}
