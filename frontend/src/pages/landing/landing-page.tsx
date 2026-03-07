import { useLocation } from 'react-router-dom';

import { LandingNavbar } from '@/components/landing/landing-navbar';
import { HeroSection } from '@/components/landing/hero-section';
import { TrustStrip } from '@/components/landing/trust-strip';
import { FeaturesBento } from '@/components/landing/features-bento';
import { HowItWorks } from '@/components/landing/how-it-works';
import { CTASection } from '@/components/landing/cta-section';
import { FooterSection } from '@/components/landing/footer-section';
import { useCriticalRoutePrefetch } from '@/features/workflow/prefetch/critical-route-prefetch';

export function LandingPage() {
  const location = useLocation();
  useCriticalRoutePrefetch({ pathname: location.pathname, projectId: null });

  return (
    <div className="min-h-screen bg-background text-foreground">
      <LandingNavbar />
      <HeroSection />
      <TrustStrip />
      <FeaturesBento />
      <HowItWorks />
      <CTASection />
      <FooterSection />
    </div>
  );
}
