const TAGS = [
  'TXT', 'EPUB', 'Markdown', 'Audiobook', 'Academic', 'Author', 'Custom Mode',
  'Multi-Character', 'Voice Mapping', 'Pronunciation', 'Analytics', 'JSON Export',
  'CSV Export', 'Chapter Detection', 'Gender Inference', 'Alias Merging',
];

export function TrustStrip() {
  const doubled = [...TAGS, ...TAGS];

  return (
    <section className="border-y border-white/10 py-5">
      <div className="pause-on-hover relative flex overflow-hidden">
        <div className="flex animate-marquee gap-3 whitespace-nowrap">
          {doubled.map((tag, i) => (
            <span
              className="inline-flex shrink-0 items-center rounded-full border border-white/10 px-3 py-1 text-xs text-muted-foreground"
              key={`${tag}-${i}`}
            >
              {tag}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
