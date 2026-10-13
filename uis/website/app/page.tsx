import React from 'react';
import dynamic from 'next/dynamic';
import { HeroSection } from './components/home/HeroSection';

const BenefitsSection = dynamic(
  () =>
    import('./components/home/BenefitsSection').then(
      (mod) => mod.BenefitsSection
    ),
  { ssr: true }
);

const HowItWorksSection = dynamic(
  () =>
    import('./components/home/HowItWorksSection').then(
      (mod) => mod.HowItWorksSection
    ),
  { ssr: true }
);

const ExperienceSection = dynamic(
  () =>
    import('./components/home/ExperienceSection').then(
      (mod) => mod.ExperienceSection
    ),
  { ssr: true }
);

/**
 * Corporate landing page (Home Route `/`) assembling all sections from Milestone 1
 * into reusable, strictly typed React components.
 *
 * @returns JSX element rendering the home page
 */
export default function HomePage(): React.ReactElement {
  return (
    <>
      <HeroSection />
      <BenefitsSection />
      <HowItWorksSection />
      <ExperienceSection />
    </>
  );
}
