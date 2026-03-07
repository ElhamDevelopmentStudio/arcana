import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

export function CTASection() {
  return (
    <section className="border-y border-white/10 bg-card px-6 py-20 text-center md:px-10">
      <div className="mx-auto max-w-2xl">
        <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
          Ready to process your first manuscript?
        </h2>
        <p className="mx-auto mt-4 text-muted-foreground">
          No setup required. Create a project, upload your source text, and get a production-ready export.
        </p>
        <div className="mt-8">
          <Link
            className="inline-flex items-center gap-2 rounded-full bg-foreground px-8 py-3 text-sm font-medium text-background transition-opacity hover:opacity-90"
            to="/projects/new"
          >
            Create your first project
            <ArrowRight size={15} />
          </Link>
        </div>
      </div>
    </section>
  );
}
