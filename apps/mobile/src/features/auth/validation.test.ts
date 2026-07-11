import { validateEmail, validateLogin, validateNewPasswords, validateSignup } from './validation';

describe('authentication validation', () => {
  it('returns exact actionable signup validation keys', () => {
    expect(validateSignup('', 'invalid', 'short')).toEqual({
      businessName: 'validation.businessNameRequired',
      email: 'validation.emailInvalid',
      password: 'validation.passwordTooShort',
    });
  });

  it('requires login credentials without exposing authentication details', () => {
    expect(validateLogin('', '')).toEqual({
      email: 'validation.emailRequired',
      password: 'validation.passwordRequired',
    });
  });

  it('rejects a structurally invalid login password before a request is sent', () => {
    expect(validateLogin('owner@example.com', 'short')).toEqual({
      password: 'validation.passwordTooShort',
    });
  });

  it('validates recovery email and matching password confirmation', () => {
    expect(validateEmail('not-an-email')).toEqual({ email: 'validation.emailInvalid' });
    expect(validateNewPasswords('new-pass-123', 'different')).toEqual({
      confirmPassword: 'validation.passwordsDoNotMatch',
    });
    expect(validateNewPasswords('new-pass-123', 'new-pass-123', '')).toEqual({
      currentPassword: 'validation.passwordRequired',
    });
  });
});
