import { type ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuthStore } from '@/store/useAuthStore';

/** Gate for public routes (like login/register): redirects authenticated users to the app. */
export function PublicOnly({ children, redirectTo = '/dashboard' }: { children: ReactNode, redirectTo?: string }) {
  const status = useAuthStore((s) => s.status);

  if (status === 'loading') {
    return null;
  }
  if (status === 'authenticated') {
    return <Navigate to={redirectTo} replace />;
  }
  return <>{children}</>;
}
