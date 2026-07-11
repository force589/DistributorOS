import '@/localization/i18n';

import { fireEvent, render } from '@testing-library/react-native';

import { InventoryOperationForm } from './InventoryOperationForm';

describe('InventoryOperationForm', () => {
  it('shows actionable required errors without submitting', async () => {
    const submit = jest.fn();
    const screen = await render(
      <InventoryOperationForm
        currentStock="5 Kg"
        loading={false}
        onSubmit={submit}
        operation="adjustment"
        productId="product-1"
      />,
    );

    await fireEvent.press(screen.getByText('Review Movement'));

    expect(screen.getByText('Quantity is required.')).toBeTruthy();
    expect(screen.getByText('Reason is required for a stock adjustment.')).toBeTruthy();
    expect(submit).not.toHaveBeenCalled();
  });

  it('submits one normalized immutable movement for confirmation', async () => {
    const submit = jest.fn();
    const screen = await render(
      <InventoryOperationForm
        currentStock="5 Kg"
        loading={false}
        onSubmit={submit}
        operation="adjustment"
        productId="product-1"
      />,
    );
    await fireEvent.changeText(screen.getByLabelText('Quantity'), '-1.250');
    await fireEvent.changeText(screen.getByLabelText('Reason'), '  Physical count  ');
    await fireEvent.press(screen.getByText('Review Movement'));

    expect(submit).toHaveBeenCalledTimes(1);
    expect(submit).toHaveBeenCalledWith({
      product_id: 'product-1',
      quantity: '-1.250',
      reason: 'Physical count',
    });
  });
});
