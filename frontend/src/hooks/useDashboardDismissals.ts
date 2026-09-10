import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as service from '@/services/dashboardService';

const KEY = ['dashboard', 'dismissals'] as const;

export function useDashboardDismissals() {
  return useQuery({ queryKey: KEY, queryFn: service.listDashboardDismissals });
}

export function useDismissDashboardItem() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: service.dismissDashboardItem,
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}

export function useClearDashboardItems() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: service.clearDashboardItems,
    onSuccess: () => client.invalidateQueries({ queryKey: KEY }),
  });
}
