import { create } from 'zustand';
import type { User } from '@/types/auth';

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthStoreState {
  /** In-memory access token (never persisted; restored via silent refresh in Phase 1). */
  token: string | null;
  user: User | null;
  status: AuthStatus;

  setAuth: (token: string, user: User) => void;
  setStatus: (status: AuthStatus) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthStoreState>((set) => ({
  token: null,
  user: null,
  status: 'loading',

  setAuth: (token, user) => set({ token, user, status: 'authenticated' }),
  setStatus: (status) => set({ status }),
  clear: () => set({ token: null, user: null, status: 'unauthenticated' }),
}));
