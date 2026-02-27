import { Users, Mic2, Play, BarChart2, BookOpen, Download } from 'lucide-react';

const FEATURES = [
  {
    icon: Users,
    title: 'Character Extraction',
    description: 'Automatically identifies every speaking character and narrator from raw text using LLM analysis.',
    image: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600&q=80&auto=format&fit=crop',
  },
  {
    icon: Mic2,
    title: 'Voice Mapping',
    description: 'Assign distinct voices to each character with intelligent gender inference and alias merging.',
    image: 'https://images.unsplash.com/photo-1590736704728-f4730bb30770?w=600&q=80&auto=format&fit=crop',
  },
  {
    icon: Play,
    title: 'Pipeline Runs',
    description: 'Trigger deterministic processing runs with full stage observability and restart support.',
    image: null,
  },
  {
    icon: BarChart2,
    title: 'Narrative Analytics',
    description: 'Inspect tension, valence, and character co-occurrence trends across chapters.',
    image: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600&q=80&auto=format&fit=crop',
  },
  {
    icon: BookOpen,
    title: 'Pronunciation Control',
    description: 'Define per-character and global pronunciation rules before any audio production export.',
    image: null,
  },
  {
    icon: Download,
    title: 'Structured Export',
    description: 'Download JSON or CSV exports ready for downstream ElevenLabs audio production workflows.',
    image: null,
  },
];

export function FeaturesBento() {
  return (
    <section className="px-6 py-24 md:px-10" id="features">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
            Everything your audiobook pipeline needs
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-muted-foreground">
            From raw manuscript to voice-ready export — all in one platform.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => {
            const Icon = feature.icon;
            return (
              <div
                className="flex flex-col gap-4 rounded-xl border border-white/10 bg-card p-5 transition-colors hover:border-white/20"
                key={feature.title}
              >
                {feature.image ? (
                  <div className="overflow-hidden rounded-lg border border-white/10">
                    <img
                      alt={feature.title}
                      className="w-full object-cover"
                      loading="lazy"
                      src={feature.image}
                      style={{ aspectRatio: '16/9' }}
                    />
                  </div>
                ) : null}
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-md border border-white/10 bg-white/5 text-muted-foreground">
                    <Icon size={14} />
                  </span>
                  <div>
                    <p className="font-semibold text-foreground">{feature.title}</p>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{feature.description}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
