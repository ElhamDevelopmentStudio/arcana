import type { RouteObject } from 'react-router-dom';

export const mainRouter: RouteObject[] = [
  {
    index: true,
    element: (
      <div className="min-h-screen bg-background">
        <main className="container mx-auto py-8">
          <h1 className="text-4xl font-bold">Welcome to NIPE</h1>
          <p className="mt-4 text-muted-foreground">
            Your comprehensive Narrative Intelligence & Performance Engine.
          </p>
        </main>
      </div>
    ),
  },
];
