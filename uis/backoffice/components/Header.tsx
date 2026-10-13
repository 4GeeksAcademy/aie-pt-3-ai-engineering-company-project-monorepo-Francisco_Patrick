'use client';

import React from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { removeToken } from '../lib/auth';
import Link from 'next/link';

/**
 * Main application navigation header component.
 *
 * @returns JSX Element rendering top bar header with navigation links and logout button.
 */
export default function Header(): React.ReactElement | null {
  const router = useRouter();
  const pathname = usePathname();

  if (pathname === '/login' || pathname === '/register') {
    return null;
  }

  const handleLogout = (): void => {
    removeToken();
    router.push('/login');
  };

  return (
    <header className="bg-slate-900 border-b border-slate-800 shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center space-x-8">
            <div className="flex-shrink-0 flex items-center">
              <Link href="/" className="text-xl font-extrabold text-emerald-400 tracking-tight">
                TrackFlow
              </Link>
            </div>
            <nav className="hidden sm:flex sm:space-x-6">
              <Link
                href="/"
                className={`${
                  pathname === '/'
                    ? 'border-emerald-500 text-white'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                } inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors`}
              >
                Dashboard
              </Link>

              <Link
                href="/incidents"
                className={`${
                  pathname?.startsWith('/incidents') && pathname !== '/incidents/register'
                    ? 'border-emerald-500 text-white'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                } inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors`}
              >
                Incidents List
              </Link>

              <Link
                href="/incidents/register"
                className={`${
                  pathname === '/incidents/register'
                    ? 'border-emerald-500 text-white'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                } inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors`}
              >
                + Register Incident
              </Link>

              <Link
                href="/inventory/products"
                className={`${
                  pathname?.startsWith('/inventory/products')
                    ? 'border-emerald-500 text-white'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                } inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors`}
              >
                Inventory
              </Link>

              <Link
                href="/inventory/orders/inbound"
                className={`${
                  pathname === '/inventory/orders/inbound'
                    ? 'border-emerald-500 text-white'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                } inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors`}
              >
                Inbound Order
              </Link>

              <Link
                href="/inventory/orders/outbound"
                className={`${
                  pathname === '/inventory/orders/outbound'
                    ? 'border-emerald-500 text-white'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                } inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors`}
              >
                Outbound Order
              </Link>

              <Link
                href="/inventory/orders"
                className={`${
                  pathname === '/inventory/orders'
                    ? 'border-emerald-500 text-white'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                } inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors`}
              >
                Orders History
              </Link>

              <Link
                href="/account/profile"
                className={`${
                  pathname === '/account/profile'
                    ? 'border-emerald-500 text-white'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                } inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors`}
              >
                Profile
              </Link>
            </nav>
          </div>
          <div className="flex items-center">
            <button
              onClick={handleLogout}
              className="ml-4 px-3.5 py-1.5 border border-slate-700 rounded-lg text-xs font-semibold text-slate-300 hover:text-white hover:bg-slate-800 focus:outline-none transition-all"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
