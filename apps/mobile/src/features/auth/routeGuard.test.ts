import { canAccessProtectedRoutes } from './AuthContext';

describe('protected route guard', () => {
  it('allows protected routes only after authentication is complete', () => {
    expect(canAccessProtectedRoutes('checking')).toBe(false);
    expect(canAccessProtectedRoutes('error')).toBe(false);
    expect(canAccessProtectedRoutes('anonymous')).toBe(false);
    expect(canAccessProtectedRoutes('authenticated')).toBe(true);
  });
});

