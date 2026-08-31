import api from './api';

export interface TelegramStatusResponse {
  status: string;
  username?: string;
  linked_at?: string;
}

export interface TelegramLinkTokenResponse {
  token: string;
  bot_url: string;
}

export async function getTelegramStatus(): Promise<TelegramStatusResponse> {
  const { data } = await api.get('/telegram/status');
  return data;
}

export async function getTelegramLinkToken(): Promise<TelegramLinkTokenResponse> {
  const { data } = await api.post('/telegram/link/token');
  return data;
}

export async function disconnectTelegram(): Promise<void> {
  await api.delete('/telegram/link');
}

export async function testTelegramNotification(): Promise<void> {
  await api.post('/telegram/test');
}
