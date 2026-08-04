import { canAccessProtectedRoutes, isSessionRestorePending } from './AuthContext';

describe('protected route guard', () => {
  it('allows protected routes only after authentication is complete', () => {
    expect(canAccessProtectedRoutes('checking')).toBe(false);
    expect(canAccessProtectedRoutes('error')).toBe(false);
    expect(canAccessProtectedRoutes('anonymous')).toBe(false);
    expect(canAccessProtectedRoutes('authenticated')).toBe(true);
  });

  it('keeps the startup route guard waiting while session restoration is in progress', () => {
    expect(isSessionRestorePending('checking')).toBe(true);
    expect(isSessionRestorePending('anonymous')).toBe(false);
    expect(isSessionRestorePending('authenticated')).toBe(false);
    expect(isSessionRestorePending('error')).toBe(false);
  });
});
