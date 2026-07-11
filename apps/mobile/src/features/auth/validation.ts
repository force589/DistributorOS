export type ValidationKey =
  | 'validation.businessNameRequired'
  | 'validation.businessNameTooLong'
  | 'validation.emailRequired'
  | 'validation.emailInvalid'
  | 'validation.passwordRequired'
  | 'validation.passwordTooShort'
  | 'validation.passwordTooLong'
  | 'validation.passwordsDoNotMatch'
  | 'validation.currentPasswordIncorrect';

export interface SignupValidationErrors {
  businessName?: ValidationKey;
  email?: ValidationKey;
  password?: ValidationKey;
}

export interface LoginValidationErrors {
  email?: ValidationKey;
  password?: ValidationKey;
}

export interface PasswordValidationErrors {
  currentPassword?: ValidationKey;
  newPassword?: ValidationKey;
  confirmPassword?: ValidationKey;
}

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateSignup(
  businessName: string,
  email: string,
  password: string,
): SignupValidationErrors {
  const errors: SignupValidationErrors = {};
  if (!businessName.trim()) {
    errors.businessName = 'validation.businessNameRequired';
  } else if (businessName.trim().length > 120) {
    errors.businessName = 'validation.businessNameTooLong';
  }
  if (!email.trim()) {
    errors.email = 'validation.emailRequired';
  } else if (!emailPattern.test(email.trim())) {
    errors.email = 'validation.emailInvalid';
  }
  if (!password) {
    errors.password = 'validation.passwordRequired';
  } else if (password.length < 8) {
    errors.password = 'validation.passwordTooShort';
  } else if (password.length > 128) {
    errors.password = 'validation.passwordTooLong';
  }
  return errors;
}

export function validateLogin(email: string, password: string): LoginValidationErrors {
  const errors: LoginValidationErrors = {};
  if (!email.trim()) {
    errors.email = 'validation.emailRequired';
  } else if (!emailPattern.test(email.trim())) {
    errors.email = 'validation.emailInvalid';
  }
  if (!password) {
    errors.password = 'validation.passwordRequired';
  } else if (password.length < 8) {
    errors.password = 'validation.passwordTooShort';
  } else if (password.length > 128) {
    errors.password = 'validation.passwordTooLong';
  }
  return errors;
}

export function validateEmail(email: string): Pick<LoginValidationErrors, 'email'> {
  if (!email.trim()) return { email: 'validation.emailRequired' };
  if (!emailPattern.test(email.trim())) return { email: 'validation.emailInvalid' };
  return {};
}

export function validateNewPasswords(
  newPassword: string,
  confirmPassword: string,
  currentPassword?: string,
): PasswordValidationErrors {
  const errors: PasswordValidationErrors = {};
  if (currentPassword !== undefined && !currentPassword) {
    errors.currentPassword = 'validation.passwordRequired';
  }
  if (!newPassword) errors.newPassword = 'validation.passwordRequired';
  else if (newPassword.length < 8) errors.newPassword = 'validation.passwordTooShort';
  else if (newPassword.length > 128) errors.newPassword = 'validation.passwordTooLong';
  if (!confirmPassword) errors.confirmPassword = 'validation.passwordRequired';
  else if (newPassword !== confirmPassword) {
    errors.confirmPassword = 'validation.passwordsDoNotMatch';
  }
  return errors;
}
