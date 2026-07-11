import { hashKey, type QueryKey } from '@tanstack/react-query';

let activeBusinessId = 'anonymous';

export function setActiveQueryBusiness(businessId: string | null): void {
  activeBusinessId = businessId ?? 'anonymous';
}

export function getActiveQueryBusiness(): string {
  return activeBusinessId;
}

export function businessQueryKey(...parts: readonly unknown[]): QueryKey {
  return ['business', activeBusinessId, ...parts];
}

export function businessQueryHash(queryKey: QueryKey): string {
  return hashKey(businessQueryKey(...queryKey));
}
