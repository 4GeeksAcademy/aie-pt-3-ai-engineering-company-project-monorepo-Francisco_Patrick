import React from 'react';
import type { Metadata } from 'next';
import './globals.css';
import { Header } from './components/layout/Header';
import { Footer } from './components/layout/Footer';

export const metadata: Metadata = {
  title: 'TrackFlow | Logística de última milla y gestión de almacenes',
  description:
    'TrackFlow unifica inventario, última milla y devoluciones para marcas e-commerce en Estados Unidos y España.',
};

export interface RootLayoutProps {
  /** Page content node */
  readonly children: React.ReactNode;
}

const ORGANIZATION_SCHEMA = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'TrackFlow',
  url: 'https://www.trackflow.example',
  description:
    'Empresa de logística de última milla y gestión de almacenes para marcas e-commerce.',
  foundingDate: '2009',
  address: [
    {
      '@type': 'PostalAddress',
      addressLocality: 'Los Angeles',
      addressCountry: 'US',
    },
    {
      '@type': 'PostalAddress',
      addressLocality: 'Zaragoza',
      addressCountry: 'ES',
    },
  ],
  contactPoint: {
    '@type': 'ContactPoint',
    contactType: 'sales',
    email: 'contacto@trackflow.example',
    availableLanguage: ['es', 'en'],
  },
  sameAs: ['https://www.linkedin.com/company/trackflow'],
};

const WEBSITE_SCHEMA = {
  '@context': 'https://schema.org',
  '@type': 'WebSite',
  name: 'TrackFlow',
  url: 'https://www.trackflow.example',
  inLanguage: ['es-ES', 'en-US'],
};

/**
 * Root public layout component providing sticky header, footer, accessibility skip links,
 * and Schema.org JSON-LD structured data.
 *
 * @param props - Layout child components
 * @returns JSX element rendering the public website shell
 */
export default function RootLayout(props: RootLayoutProps): React.ReactElement {
  return (
    <html lang="es">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(ORGANIZATION_SCHEMA) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(WEBSITE_SCHEMA) }}
        />
      </head>
      <body className="bg-slate-950 text-slate-100 antialiased">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-cyan-300 focus:px-4 focus:py-2 focus:text-slate-950"
        >
          Saltar al contenido principal
        </a>

        <Header />

        <main id="main-content">{props.children}</main>

        <Footer />
      </body>
    </html>
  );
}
