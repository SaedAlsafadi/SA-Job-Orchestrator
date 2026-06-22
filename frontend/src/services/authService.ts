import api from '@/services/api';
import type { RegisterRequest, TokenResponse, User } from '@/types/auth';

/** Authentication API calls. */
export const authService = {
  async register(data: RegisterRequest): Promise<User> {
    const res = await api.post<User>('/auth/register', data);
    return res.data;
  },

  /** Log in via the OAuth2 password flow (form-encoded username/password). */
  async login(email: string, password: string): Promise<TokenResponse> {
    const form = new URLSearchParams();
    form.append('username', email);
    form.append('password', password);
    const res = await api.post<TokenResponse>('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return res.data;
  },

  async me(): Promise<User> {
    const res = await api.get<User>('/auth/me');
    return res.data;
  },

  /** Silent refresh via the httpOnly refresh cookie. Endpoint lands in Phase 1. */
  async refresh(): Promise<TokenResponse> {
    const res = await api.post<TokenResponse>('/auth/refresh');
    return res.data;
  },

  /** Short-lived ticket for authenticating the WebSocket handshake. */
  async getWsTicket(): Promise<string> {
    const res = await api.get<{ ticket: string }>('/auth/ws-ticket');
    return res.data.ticket;
  },
};
