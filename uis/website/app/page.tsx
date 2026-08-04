import React from 'react';
import { HeroSection } from './components/home/HeroSection';
import { BenefitsSection } from './components/home/BenefitsSection';
import { HowItWorksSection } from './components/home/HowItWorksSection';
import { ExperienceSection } from './components/home/ExperienceSection';

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
