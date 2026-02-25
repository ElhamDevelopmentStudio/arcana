import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function AuthPlaceholderPage() {
  return (
    <div className="mx-auto mt-12 w-full max-w-xl">
      <Card>
        <CardHeader>
          <CardTitle>Authentication Placeholder</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Auth flow is intentionally staged for a later task. Route wiring is present so future auth work can plug in without route restructuring.
        </CardContent>
      </Card>
    </div>
  );
}
