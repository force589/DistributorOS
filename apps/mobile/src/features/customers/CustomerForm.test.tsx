import '@/localization/i18n';

import { fireEvent, render } from '@testing-library/react-native';

import { CustomerForm } from './CustomerForm';

describe('CustomerForm', () => {
  it('shows an actionable name error and does not submit invalid data', async () => {
    const submit = jest.fn().mockResolvedValue(undefined);
    const screen = await render(
      <CustomerForm
        actionLabel="Create Customer"
        loading={false}
        loadingLabel="Creating Customer…"
        onSubmit={submit}
      />,
    );

    await fireEvent.press(screen.getByText('Create Customer'));

    expect(screen.getByText('Customer name is required.')).toBeTruthy();
    expect(submit).not.toHaveBeenCalled();
  });

  it('normalizes and submits valid customer information once', async () => {
    const submit = jest.fn().mockResolvedValue(undefined);
    const screen = await render(
      <CustomerForm
        actionLabel="Create Customer"
        loading={false}
        loadingLabel="Creating Customer…"
        onSubmit={submit}
      />,
    );
    await fireEvent.changeText(screen.getByLabelText('Customer Name'), '  Mango Corner  ');
    await fireEvent.changeText(screen.getByLabelText('Phone'), '+91 98765 43210');

    await fireEvent.press(screen.getByText('Create Customer'));

    expect(submit).toHaveBeenCalledTimes(1);
    expect(submit).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Mango Corner', phone: '+91 98765 43210' }),
    );
  });
});
