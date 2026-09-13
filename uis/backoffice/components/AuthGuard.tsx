'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { isAuthenticated } from '../lib/auth';

const PUBLIC_PATHS: readonly string[] = [
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
];

export interface AuthGuardProps {
  readonly children: React.ReactNode;
}

/**
 * Route protection guard enforcing authentication checks while allowing public access to login and recovery paths.
 *
 * @param props - Child component elements to wrap.
 * @returns JSX Element rendering children if authorized, or loading spinner.
 */
export default function AuthGuard(props: AuthGuardProps): React.ReactElement {
  const { children } = props;
  const router = useRouter();
  const pathname = usePathname();
  const [authorized, setAuthorized] = useState<boolean>(false);

  useEffect(() => {
    const isPublic = PUBLIC_PATHS.some(
      (path) => pathname === path || pathname.startsWith(`${path}/`)
    );

    if (isPublic) {
      setAuthorized(true);
      return;
    }

    if (!isAuthenticated()) {
      setAuthorized(false);
      router.push('/login');
    } else {
      setAuthorized(true);
    }
  }, [pathname, router]);

  if (!authorized) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-gray-50">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
      </div>
    );
  }

  return <>{children}</>;
}

