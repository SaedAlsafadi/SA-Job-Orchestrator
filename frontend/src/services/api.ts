import axios from 'axios';
import type { ApiError } from '@/types/api';
import { useAuthStore } from '@/store/useAuthStore';

/** Pre-configured Axios instance pointing at the backend API. */
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000,
  // Send the httpOnly refresh cookie on auth requests.
  withCredentials: true,
});

/** Attach a trace-id and the bearer token to every outgoing request. */
api.interceptors.request.use((config) => {
  config.headers['X-Trace-Id'] = crypto.randomUUID();
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

/** Normalize errors; clear auth on 401 so the app redirects to /login.
 *
 * (Single-flight refresh against `/auth/refresh` lands in Phase 1; until then an
 * expired/invalid access token simply de-authenticates the session.)
 */
api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response) {
      const status = error.response.status;
      const url = error.config?.url ?? '';
      const isAuthEntry = url.includes('/auth/login') || url.includes('/auth/register');
      if (status === 401 && !isAuthEntry) {
        useAuthStore.getState().clear();
      }
      const data = error.response.data as Record<string, unknown>;
      const apiError: ApiError = {
        detail: typeof data['detail'] === 'string' ? data['detail'] : 'An unexpected error occurred',
        status_code: status,
        trace_id: typeof data['trace_id'] === 'string' ? data['trace_id'] : undefined,
      };
      return Promise.reject(apiError);
    }
    const fallback: ApiError = {
      detail: 'Network error. Please check your connection.',
      status_code: 0,
    };
    return Promise.reject(fallback);
  },
);

export default api;
