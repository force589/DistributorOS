import type { CustomerCreateRequest } from '@distributoros/api-client';

export type CustomerField = keyof CustomerCreateRequest;
export type CustomerValidationKey =
  | 'customers.validation.nameRequired'
  | 'customers.validation.nameTooLong'
  | 'customers.validation.phoneInvalid'
  | 'customers.validation.emailInvalid'
  | 'customers.validation.addressTooLong'
  | 'customers.validation.cityTooLong'
  | 'customers.validation.stateTooLong'
  | 'customers.validation.postalCodeTooLong'
  | 'customers.validation.notesTooLong';

export type CustomerValidationErrors = Partial<Record<CustomerField, CustomerValidationKey>>;

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const phonePattern = /^\+?[0-9][0-9 ()-]*$/;

export function validateCustomer(
  customer: CustomerCreateRequest,
): CustomerValidationErrors {
  const errors: CustomerValidationErrors = {};
  const name = customer.name.trim();
  if (!name) {
    errors.name = 'customers.validation.nameRequired';
  } else if (name.length > 160) {
    errors.name = 'customers.validation.nameTooLong';
  }

  const phone = customer.phone?.trim();
  if (phone) {
    const digits = phone.replace(/\D/g, '');
    if (digits.length < 7 || digits.length > 15 || !phonePattern.test(phone)) {
      errors.phone = 'customers.validation.phoneInvalid';
    }
  }

  const email = customer.email?.trim();
  if (email && !emailPattern.test(email)) {
    errors.email = 'customers.validation.emailInvalid';
  }
  if ((customer.address_line_1?.trim().length ?? 0) > 200) {
    errors.address_line_1 = 'customers.validation.addressTooLong';
  }
  if ((customer.address_line_2?.trim().length ?? 0) > 200) {
    errors.address_line_2 = 'customers.validation.addressTooLong';
  }
  if ((customer.city?.trim().length ?? 0) > 100) {
    errors.city = 'customers.validation.cityTooLong';
  }
  if ((customer.state?.trim().length ?? 0) > 100) {
    errors.state = 'customers.validation.stateTooLong';
  }
  if ((customer.postal_code?.trim().length ?? 0) > 20) {
    errors.postal_code = 'customers.validation.postalCodeTooLong';
  }
  if ((customer.notes?.trim().length ?? 0) > 2000) {
    errors.notes = 'customers.validation.notesTooLong';
  }
  return errors;
}

export function normalizeCustomer(
  customer: CustomerCreateRequest,
): CustomerCreateRequest {
  const optional = (value: string | null | undefined): string | null => {
    const normalized = value?.trim();
    return normalized ? normalized : null;
  };
  return {
    name: customer.name.trim(),
    phone: optional(customer.phone),
    email: optional(customer.email),
    address_line_1: optional(customer.address_line_1),
    address_line_2: optional(customer.address_line_2),
    city: optional(customer.city),
    state: optional(customer.state),
    postal_code: optional(customer.postal_code),
    notes: optional(customer.notes),
  };
}
