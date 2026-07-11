import type { AuthResponse } from '@distributoros/api-client';

import {
  coordinateWebRefresh,
  resetWebSessionCoordinatorForTests,
} from './webSessionCoordinator';

const session: AuthResponse = {
  access_token: 'access-token',
  expires_in: 900,
  refresh_token: null,
  token_type: 'bearer',
  user: {
    id: '00000000-0000-0000-0000-000000000001',
    email: 'owner@example.com',
    business: {
      id: '00000000-0000-0000-0000-000000000002',
      business_name: 'Business',
      currency: 'INR',
      language: 'en',
      theme: 'system',
      timezone: 'Asia/Kolkata',
    },
  },
};

describe('cross-tab session refresh coordination', () => {
  afterEach(() => {
    resetWebSessionCoordinatorForTests();
    Object.defineProperty(navigator, 'locks', {
      configurable: true,
      value: undefined,
    });
  });

  it('allows only one refresh call while concurrent tabs share its result', async () => {
    let queue = Promise.resolve();
    Object.defineProperty(navigator, 'locks', {
      configurable: true,
      value: {
        request: <T,>(_name: string, callback: () => Promise<T>): Promise<T> => {
          const result = queue.then(callback);
          queue = result.then(() => undefined);
          return result;
        },
      },
    });
    const refresh = jest.fn().mockResolvedValue(session);
    const [first, second] = await Promise.all([
      coordinateWebRefresh(refresh),
      coordinateWebRefresh(refresh),
    ]);
    expect(first).toEqual(session);
    expect(second).toEqual(session);
    expect(refresh).toHaveBeenCalledTimes(1);
  });
});
