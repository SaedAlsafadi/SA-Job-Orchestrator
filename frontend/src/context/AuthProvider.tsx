import { useEffect, type ReactNode } from 'react';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';

import { authService } from '@/services/authService';
import { useAuthStore } from '@/store/useAuthStore';

/**
 * Initializes auth state on boot via a silent refresh (httpOnly cookie). In Phase 0
 * the `/auth/refresh` endpoint does not exist yet, so boot resolves to
 * "unauthenticated" and the user logs in explicitly; Phase 1 enables persistence.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const status = useAuthStore((s) => s.status);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const { access_token } = await authService.refresh();
        // Attach the token (keep status 'loading') so the me() call is authenticated.
        useAuthStore.setState({ token: access_token });
        const user = await authService.me();
        if (active) {
          useAuthStore.getState().setAuth(access_token, user);
        }
      } catch {
        if (active) {
          useAuthStore.getState().clear();
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  if (status === 'loading') {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  return <>{children}</>;
}
