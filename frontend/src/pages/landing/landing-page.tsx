import { useLocation } from 'react-router-dom';

import { CTASection } from '@/components/landing/cta-section';
import { FeaturesSection } from '@/components/landing/features-section';
import { FooterSection } from '@/components/landing/footer-section';
import { HeroSection } from '@/components/landing/hero-section';
import { IntegrationsSection } from '@/components/landing/integrations-section';
import { StatsSection } from '@/components/landing/stats-section';
import { useCriticalRoutePrefetch } from '@/features/workflow/prefetch/critical-route-prefetch';
import {
  useHealthQuery,
  useModeCatalogQuery,
  useProjectControlPanelSummaryQuery,
} from '@/features/workflow/api/workflow-hooks';

export function LandingPage() {
  const location = useLocation();
  const healthQuery = useHealthQuery(true);
  const modeCatalogQuery = useModeCatalogQuery(true);
  const controlPanelSummaryQuery = useProjectControlPanelSummaryQuery(true);

  useCriticalRoutePrefetch({
    pathname: location.pathname,
    projectId: null,
  });

  return (
    <main className="min-h-screen bg-background text-foreground">
      <HeroSection healthStatus={healthQuery.data?.status ?? null} />
      <StatsSection summary={controlPanelSummaryQuery.data ?? null} />
      <FeaturesSection />
      <IntegrationsSection modeCatalog={modeCatalogQuery.data ?? null} />
      <CTASection />
      <FooterSection />
    </main>
  );
}
