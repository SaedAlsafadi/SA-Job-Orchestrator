import api from './api';

export interface DashboardDismissal {
  id: string;
  entity_type: 'application' | 'activity';
  entity_id: string;
  fingerprint: string;
  dismissed_at: string;
}

export const dashboardFingerprint = (status: string, updatedAt: string) => `${status}:${updatedAt}`;

export async function listDashboardDismissals(): Promise<DashboardDismissal[]> {
  const { data } = await api.get<{ items: DashboardDismissal[] }>('/dashboard/dismissals');
  return data.items;
}

export async function dismissDashboardItem(payload: Pick<DashboardDismissal, 'entity_type' | 'entity_id' | 'fingerprint'>): Promise<DashboardDismissal> {
  const { data } = await api.post<DashboardDismissal>('/dashboard/dismissals', payload);
  return data;
}

export async function clearDashboardItems(entityType: 'application' | 'activity'): Promise<void> {
  await api.delete('/dashboard/dismissals', { params: { entity_type: entityType } });
}
