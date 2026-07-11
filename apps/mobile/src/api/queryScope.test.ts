import { QueryClient } from '@tanstack/react-query';

import {
  businessQueryKey,
  businessQueryHash,
  getActiveQueryBusiness,
  setActiveQueryBusiness,
} from './queryScope';

describe('business query isolation', () => {
  afterEach(() => setActiveQueryBusiness(null));

  it('namespaces identical domain keys by business', () => {
    setActiveQueryBusiness('business-a');
    const businessA = businessQueryKey('customers');
    setActiveQueryBusiness('business-b');
    const businessB = businessQueryKey('customers');

    expect(businessA).toEqual(['business', 'business-a', 'customers']);
    expect(businessB).toEqual(['business', 'business-b', 'customers']);
    expect(businessA).not.toEqual(businessB);
  });

  it('leaves no previous-business data after a session boundary clear', () => {
    const client = new QueryClient({
      defaultOptions: { queries: { queryKeyHashFn: businessQueryHash } },
    });
    setActiveQueryBusiness('business-a');
    client.setQueryData(businessQueryKey('customers'), ['Business A customer']);

    client.clear();
    setActiveQueryBusiness('business-b');

    expect(getActiveQueryBusiness()).toBe('business-b');
    expect(client.getQueryData(businessQueryKey('customers'))).toBeUndefined();
    expect(client.getQueryCache().getAll()).toHaveLength(0);
  });

  it('cannot resolve another business cache entry even before explicit cleanup', () => {
    const client = new QueryClient({
      defaultOptions: { queries: { queryKeyHashFn: businessQueryHash } },
    });
    setActiveQueryBusiness('business-a');
    client.setQueryData(['dashboard'], { business: 'A' });

    setActiveQueryBusiness('business-b');

    expect(client.getQueryData(['dashboard'])).toBeUndefined();
    client.clear();
  });
});
