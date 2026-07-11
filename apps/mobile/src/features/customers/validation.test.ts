import type { CustomerCreateRequest } from '@distributoros/api-client';

import { normalizeCustomer, validateCustomer } from './validation';

const validCustomer: CustomerCreateRequest = {
  name: 'Mango Corner',
  phone: '+91 98765 43210',
  email: 'orders@mangocorner.in',
  address_line_1: 'Market Road',
  address_line_2: null,
  city: 'Kochi',
  state: 'Kerala',
  postal_code: '682001',
  notes: 'Morning delivery',
};

describe('customer validation', () => {
  it('accepts valid customer information', () => {
    expect(validateCustomer(validCustomer)).toEqual({});
  });

  it('returns field-specific keys for every customer rule', () => {
    expect(
      validateCustomer({
        name: ' ',
        phone: '12-ab',
        email: 'invalid',
        address_line_1: 'x'.repeat(201),
        address_line_2: 'x'.repeat(201),
        city: 'x'.repeat(101),
        state: 'x'.repeat(101),
        postal_code: 'x'.repeat(21),
        notes: 'x'.repeat(2001),
      }),
    ).toEqual({
      name: 'customers.validation.nameRequired',
      phone: 'customers.validation.phoneInvalid',
      email: 'customers.validation.emailInvalid',
      address_line_1: 'customers.validation.addressTooLong',
      address_line_2: 'customers.validation.addressTooLong',
      city: 'customers.validation.cityTooLong',
      state: 'customers.validation.stateTooLong',
      postal_code: 'customers.validation.postalCodeTooLong',
      notes: 'customers.validation.notesTooLong',
    });
    expect(validateCustomer({ name: 'x'.repeat(161) })).toEqual({
      name: 'customers.validation.nameTooLong',
    });
  });

  it('trims values and converts blank optional fields to null', () => {
    expect(
      normalizeCustomer({
        ...validCustomer,
        name: '  Mango Corner  ',
        email: ' ',
        notes: '  Morning delivery  ',
      }),
    ).toMatchObject({
      name: 'Mango Corner',
      email: null,
      notes: 'Morning delivery',
    });
  });
});
