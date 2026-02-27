export function FooterSection() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="border-t border-panel-border/80 px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-2 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p>NIPE shared workspace (no authentication enabled)</p>
        <p>© {currentYear} NIPE</p>
      </div>
    </footer>
  );
}

