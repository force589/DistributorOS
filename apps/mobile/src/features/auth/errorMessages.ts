import { ApiError } from '@distributoros/api-client';

import type { LoginValidationErrors, SignupValidationErrors } from './validation';

export type ErrorTranslationKey =
  | 'errors.emailRegistered'
  | 'errors.invalidCredentials'
  | 'errors.sessionExpired'
  | 'errors.businessAccess'
  | 'errors.forbidden'
  | 'errors.notFound'
  | 'errors.network'
  | 'errors.server'
  | 'errors.validation'
  | 'errors.currencyChangeRestricted'
  | 'errors.rateLimited'
  | 'errors.passwordResetInvalid'
  | 'errors.currentPasswordIncorrect'
  | 'errors.passwordUnchanged'
  | 'errors.unknown';

const errorKeys: Record<string, ErrorTranslationKey> = {
  EMAIL_ALREADY_REGISTERED: 'errors.emailRegistered',
  INVALID_CREDENTIALS: 'errors.invalidCredentials',
  SESSION_EXPIRED: 'errors.sessionExpired',
  AUTHENTICATION_REQUIRED: 'errors.sessionExpired',
  BUSINESS_ACCESS_REQUIRED: 'errors.businessAccess',
  FORBIDDEN: 'errors.forbidden',
  UNTRUSTED_ORIGIN: 'errors.forbidden',
  NOT_FOUND: 'errors.notFound',
  NETWORK_ERROR: 'errors.network',
  INTERNAL_SERVER_ERROR: 'errors.server',
  VALIDATION_ERROR: 'errors.validation',
  CURRENCY_CHANGE_RESTRICTED: 'errors.currencyChangeRestricted',
  RATE_LIMIT_EXCEEDED: 'errors.rateLimited',
  PASSWORD_RESET_LINK_INVALID: 'errors.passwordResetInvalid',
  CURRENT_PASSWORD_INCORRECT: 'errors.currentPasswordIncorrect',
  PASSWORD_UNCHANGED: 'errors.passwordUnchanged',
};

export function getErrorTranslationKey(error: unknown): ErrorTranslationKey {
  if (error instanceof ApiError) {
    return errorKeys[error.code] ?? (error.status >= 500 ? 'errors.server' : 'errors.unknown');
  }
  return 'errors.unknown';
}

function passwordValidationKey(message: string) {
  const normalized = message.toLowerCase();
  if (normalized.includes('required')) return 'validation.passwordRequired' as const;
  if (normalized.includes('128') || normalized.includes('long')) {
    return 'validation.passwordTooLong' as const;
  }
  return 'validation.passwordTooShort' as const;
}

export function getSignupValidationErrors(error: unknown): SignupValidationErrors {
  if (!(error instanceof ApiError) || error.code !== 'VALIDATION_ERROR') return {};
  const validationErrors: SignupValidationErrors = {};
  if (error.fieldErrors.business_name) {
    validationErrors.businessName = error.fieldErrors.business_name.includes('120')
      ? 'validation.businessNameTooLong'
      : 'validation.businessNameRequired';
  }
  if (error.fieldErrors.email) validationErrors.email = 'validation.emailInvalid';
  if (error.fieldErrors.password) {
    validationErrors.password = passwordValidationKey(error.fieldErrors.password);
  }
  return validationErrors;
}

export function getLoginValidationErrors(error: unknown): LoginValidationErrors {
  if (!(error instanceof ApiError) || error.code !== 'VALIDATION_ERROR') return {};
  const validationErrors: LoginValidationErrors = {};
  if (error.fieldErrors.email) validationErrors.email = 'validation.emailInvalid';
  if (error.fieldErrors.password) {
    validationErrors.password = passwordValidationKey(error.fieldErrors.password);
  }
  return validationErrors;
}
