import React from 'react';
import Link from 'next/link';

export interface NavItem {
  readonly label: string;
  readonly href: string;
  readonly isCTA?: boolean;
}

export interface HeaderProps {
  /** Optional custom list of navigation links */
  readonly navItems?: readonly NavItem[];
}

const DEFAULT_NAV_ITEMS: readonly NavItem[] = [
  { label: 'Beneficios', href: '/#beneficios' },
  { label: 'Cómo funciona', href: '/#como-funciona' },
  { label: 'Experiencia', href: '/#experiencia' },
  { label: 'Application', href: '/application' },
  { label: 'Contacto', href: '/#contacto', isCTA: true },
];

/**
 * Global public header component with sticky positioning, keyboard navigation,
 * and responsive brand layout.
 *
 * @param props - Configuration properties for navigation items
 * @returns JSX element rendering the header bar
 */
export function Header(props: HeaderProps): React.ReactElement {
  const items = props.navItems ?? DEFAULT_NAV_ITEMS;

  return (
    <header
      className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/95 backdrop-blur"
      role="banner"
    >
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="flex items-center gap-3 rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"
          aria-label="Ir a la página principal de TrackFlow"
        >
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-400 text-lg font-bold text-slate-950">
            TF
          </span>
          <div>
            <p className="text-lg font-semibold tracking-tight text-slate-100">
              TrackFlow
            </p>
            <p className="text-xs text-slate-400">
              Last-mile logistics and warehouse intelligence
            </p>
          </div>
        </Link>

        <nav aria-label="Navegación principal">
          <ul className="flex items-center gap-2 text-sm sm:gap-4">
            {items.map((item) => (
              <li key={item.href}>
                {item.isCTA === true ? (
                  <Link
                    href={item.href}
                    className="rounded-md bg-cyan-400 px-3 py-2 font-medium text-slate-950 hover:bg-cyan-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-100"
                  >
                    {item.label}
                  </Link>
                ) : (
                  <Link
                    href={item.href}
                    className="rounded-md px-3 py-2 text-slate-300 hover:bg-slate-800 hover:text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"
                  >
                    {item.label}
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
