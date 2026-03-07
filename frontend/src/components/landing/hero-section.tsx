import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

export function HeroSection() {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 pt-14 text-center">
      {/* Ambient blobs */}
      <div
        aria-hidden
        className="pointer-events-none absolute bottom-0 left-0 h-[600px] w-[600px] -translate-x-1/3 translate-y-1/4 rounded-full opacity-70"
        style={{
          background: 'radial-gradient(circle, oklch(0.488 0.243 264.376 / 0.07) 0%, transparent 70%)',
          filter: 'blur(80px)',
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute right-0 top-0 h-[500px] w-[500px] translate-x-1/3 -translate-y-1/4 rounded-full opacity-70"
        style={{
          background: 'radial-gradient(circle, oklch(0.75 0.18 65 / 0.06) 0%, transparent 70%)',
          filter: 'blur(100px)',
        }}
      />

      <div className="relative z-10 mx-auto max-w-4xl animate-fade-in-up">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-muted-foreground">
          <span className="inline-block size-1.5 rounded-full bg-green-400/80" />
          Audiobook pipeline · Character extraction · Voice mapping
        </div>

        <h1 className="text-5xl font-bold tracking-tight text-foreground md:text-6xl lg:text-7xl">
          Bring Any Story
          <br />
          <span className="text-muted-foreground">to Life</span>
        </h1>

        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
          Upload a novel, academic paper, or manuscript. Nipe extracts characters, maps voices,
          and produces a fully-tagged audiobook-ready export in minutes.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Link
            className="inline-flex items-center gap-2 rounded-full bg-foreground px-6 py-2.5 text-sm font-medium text-background transition-opacity hover:opacity-90"
            to="/projects/new"
          >
            Start a Project
            <ArrowRight size={15} />
          </Link>
          <a
            className="inline-flex items-center gap-2 rounded-full border border-white/15 px-6 py-2.5 text-sm text-muted-foreground transition-colors hover:border-white/30 hover:text-foreground"
            href="#how-it-works"
          >
            See how it works
          </a>
        </div>
      </div>

      {/* Hero image */}
      <div className="relative z-10 mx-auto mt-16 w-full max-w-5xl animate-fade-in px-4">
        <div className="overflow-hidden rounded-xl border border-white/10">
          <img
            alt="Nipe dashboard preview"
            className="w-full object-cover"
            loading="eager"
            src="https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=1200&q=80&auto=format&fit=crop"
            style={{ aspectRatio: '16/9' }}
          />
        </div>
      </div>
    </section>
  );
}
