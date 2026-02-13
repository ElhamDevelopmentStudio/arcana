import type { ModeCatalogDto } from '@/app/schemas/api';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

type IntegrationsSectionProps = {
  modeCatalog: ModeCatalogDto | null;
};

export function IntegrationsSection({ modeCatalog }: IntegrationsSectionProps) {
  const modes = modeCatalog?.modes ?? [];

  return (
    <section className="px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-6xl space-y-4">
        <div className="space-y-2">
          <h2 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">Mode profiles and outputs</h2>
          <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
            Live mode catalog values are loaded from the backend and shown here with profile intent and export formats.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {modes.length === 0 ? (
            <Card className="sm:col-span-2 lg:col-span-4">
              <CardHeader>
                <CardTitle>Mode catalog unavailable</CardTitle>
                <CardDescription>Unable to fetch `/api/modes` right now. Try again from Dashboard.</CardDescription>
              </CardHeader>
              <CardContent />
            </Card>
          ) : (
            modes.map((mode) => {
              const profile = modeCatalog?.mode_profiles?.[mode];
              return (
                <Card key={mode}>
                  <CardHeader>
                    <CardTitle className="capitalize">{mode}</CardTitle>
                    <CardDescription>{profile?.profile_intent ?? 'No profile intent provided.'}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <p className="text-xs text-muted-foreground">Export formats</p>
                    <div className="flex flex-wrap gap-1">
                      {(profile?.export_formats ?? []).map((format) => (
                        <Badge key={`${mode}-${format}`} variant="secondary">
                          {format}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>
      </div>
    </section>
  );
}

