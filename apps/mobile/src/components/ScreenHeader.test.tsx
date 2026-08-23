import { fireEvent, render } from '@testing-library/react-native';

import { ScreenHeader } from './ScreenHeader';

jest.mock('@/navigation/UnsavedChangesContext', () => ({
  useUnsavedChanges: () => ({
    guardNavigation: (action: () => void) => action(),
  }),
}));

describe('ScreenHeader navigation level', () => {
  it('does not render Back for primary destinations', async () => {
    const onBack = jest.fn();
    const screen = await render(
      <ScreenHeader
        backLabel="Back"
        level="primary"
        onBack={onBack}
        title="Customers"
      />,
    );

    expect(screen.queryByText('Back')).toBeNull();
    expect(screen.getByRole('header', { name: 'Customers' }).props['aria-level']).toBe(1);
  });

  it('keeps Back for nested destinations', async () => {
    const onBack = jest.fn();
    const screen = await render(
      <ScreenHeader
        backLabel="Back"
        onBack={onBack}
        title="Customer Details"
      />,
    );

    fireEvent.press(screen.getByRole('button', { name: 'Back' }));

    expect(onBack).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('header', { name: 'Customer Details' }).props['aria-level']).toBe(1);
  });
});
