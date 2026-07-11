import '@/localization/i18n';

import { fireEvent, render } from '@testing-library/react-native';

import { SaleForm } from './SaleForm';

jest.mock('@tanstack/react-query', () => ({
  keepPreviousData: undefined,
  useQuery: jest.fn(() => ({ data: { items: [] }, isError: false, isFetching: false })),
}));

describe('SaleForm', () => {
  it('shows actionable required errors without submitting', async () => {
    const submit = jest.fn();
    const screen = await render(
      <SaleForm
        actionLabel="Create Draft"
        loading={false}
        loadingLabel="Creating Draft…"
        onSubmit={submit}
      />,
    );

    await fireEvent.press(screen.getByText('Create Draft'));

    expect(screen.getByText('Select a customer for this sale.')).toBeTruthy();
    expect(screen.getByText('Add at least one product to this sale.')).toBeTruthy();
    expect(submit).not.toHaveBeenCalled();
    screen.unmount();
  });
});
