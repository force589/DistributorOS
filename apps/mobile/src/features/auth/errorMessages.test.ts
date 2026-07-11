import { ApiError } from '@distributoros/api-client';

import { getLoginValidationErrors, getSignupValidationErrors } from './errorMessages';

describe('authentication API validation errors', () => {
  it('maps signup field errors to localized, actionable validation keys', () => {
    const error = new ApiError(422, 'VALIDATION_ERROR', 'Invalid request', {
      business_name: 'Business name is required.',
      email: 'Please enter a valid email.',
      password: 'Password must contain at least 8 characters.',
    });

    expect(getSignupValidationErrors(error)).toEqual({
      businessName: 'validation.businessNameRequired',
      email: 'validation.emailInvalid',
      password: 'validation.passwordTooShort',
    });
  });

  it('maps login field errors without exposing backend text', () => {
    const error = new ApiError(422, 'VALIDATION_ERROR', 'Invalid request', {
      email: 'Backend-specific text',
      password: 'Password is too long (maximum 128 characters).',
    });

    expect(getLoginValidationErrors(error)).toEqual({
      email: 'validation.emailInvalid',
      password: 'validation.passwordTooLong',
    });
  });
});
