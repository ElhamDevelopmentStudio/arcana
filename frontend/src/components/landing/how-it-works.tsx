const STEPS = [
  {
    number: '01',
    title: 'Upload',
    description:
      'Drop your TXT, EPUB, or Markdown file. Nipe ingests it, normalizes the text, and detects chapter boundaries automatically.',
    image: 'https://images.unsplash.com/photo-1618044733300-9472054094ee?w=600&q=80&auto=format&fit=crop',
  },
  {
    number: '02',
    title: 'Configure',
    description:
      'Set the processing mode, define characters, assign voices, and tune pipeline parameters to match your production requirements.',
    image: 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=600&q=80&auto=format&fit=crop',
  },
  {
    number: '03',
    title: 'Export',
    description:
      'Trigger a run and download your fully-tagged, voice-ready JSON or CSV export when it completes. Ready for ElevenLabs or any TTS pipeline.',
    image: 'https://images.unsplash.com/photo-1614624532983-4ce03382d63d?w=600&q=80&auto=format&fit=crop',
  },
];

export function HowItWorks() {
  return (
    <section className="px-6 py-24 md:px-10" id="how-it-works">
      <div className="mx-auto max-w-6xl">
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
            From manuscript to production in three steps
          </h2>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          {STEPS.map((step) => (
            <div
              className="flex flex-col gap-4 rounded-xl border border-white/10 bg-card p-6"
              key={step.number}
            >
              <div className="overflow-hidden rounded-lg border border-white/10">
                <img
                  alt={step.title}
                  className="w-full object-cover"
                  loading="lazy"
                  src={step.image}
                  style={{ aspectRatio: '16/9' }}
                />
              </div>
              <div>
                <span className="font-mono text-3xl font-bold text-white/10">{step.number}</span>
                <h3 className="mt-1 text-lg font-semibold text-foreground">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
