import { Link } from 'react-router-dom';
import { BookOpenText } from 'lucide-react';

const FOOTER_LINKS = [
  {
    heading: 'Product',
    links: [
      { label: 'Dashboard', to: '/dashboard' },
      { label: 'New Project', to: '/projects/new' },
    ],
  },
  {
    heading: 'Resources',
    links: [
      { label: 'API Reference', to: '#' },
      { label: 'Changelog', to: '#' },
    ],
  },
  {
    heading: 'Modes',
    links: [
      { label: 'Audiobook', to: '#' },
      { label: 'Academic', to: '#' },
      { label: 'Author', to: '#' },
      { label: 'Custom', to: '#' },
    ],
  },
  {
    heading: 'Legal',
    links: [
      { label: 'Privacy', to: '#' },
      { label: 'Terms', to: '#' },
    ],
  },
];

export function FooterSection() {
  return (
    <footer className="px-6 py-16 md:px-10">
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-10 md:grid-cols-5">
          {/* Brand */}
          <div className="md:col-span-1">
            <Link className="flex items-center gap-2" to="/">
              <span className="grid size-7 place-items-center rounded bg-foreground text-background">
                <BookOpenText size={14} />
              </span>
              <span className="text-sm font-semibold text-foreground">nipe</span>
            </Link>
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
              Audiobook pipeline for narrative intelligence.
            </p>
          </div>

          {/* Link columns */}
          {FOOTER_LINKS.map((col) => (
            <div key={col.heading}>
              <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground/60">
                {col.heading}
              </p>
              <ul className="space-y-2">
                {col.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                      to={link.to}
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-8 text-xs text-muted-foreground">
          <p>© 2025 Nipe. Built for audiobook creators.</p>
          <p>Narrative Intelligence & Performance Engine</p>
        </div>
      </div>
    </footer>
  );
}
