'use client';

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpenText } from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV_LINKS = [
  { label: 'Features', href: '#features' },
  { label: 'How it Works', href: '#how-it-works' },
  { label: 'Modes', href: '#modes' },
];

export function LandingNavbar() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <header
      className={cn(
        'fixed inset-x-0 top-0 z-50 flex h-14 items-center px-6 transition-all duration-300 md:px-10',
        scrolled
          ? 'border-b border-white/10 bg-background/80 backdrop-blur-md'
          : 'bg-transparent',
      )}
    >
      {/* Logo */}
      <Link className="flex items-center gap-2" to="/">
        <span className="grid size-7 place-items-center rounded bg-foreground text-background">
          <BookOpenText size={14} />
        </span>
        <span className="text-sm font-semibold tracking-tight text-foreground">nipe</span>
      </Link>

      {/* Center nav */}
      <nav className="mx-auto hidden items-center gap-6 md:flex">
        {NAV_LINKS.map((link) => (
          <a
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            href={link.href}
            key={link.label}
          >
            {link.label}
          </a>
        ))}
      </nav>

      {/* CTAs */}
      <div className="ml-auto flex items-center gap-2">
        <Link
          className="hidden rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground md:inline-flex"
          to="/dashboard"
        >
          Sign in
        </Link>
        <Link
          className="inline-flex items-center rounded-full bg-foreground px-4 py-1.5 text-sm font-medium text-background transition-opacity hover:opacity-90"
          to="/dashboard"
        >
          Get started
        </Link>
      </div>
    </header>
  );
}
