import '@/localization/i18n';

import { fireEvent, render } from '@testing-library/react-native';

import { ProductForm } from './ProductForm';

describe('ProductForm', () => {
  it('shows required field errors and does not submit incomplete data', async () => {
    const submit = jest.fn().mockResolvedValue(undefined);
    const screen = await render(
      <ProductForm
        actionLabel="Create Product"
        loading={false}
        loadingLabel="Creating Product…"
        onSubmit={submit}
      />,
    );

    await fireEvent.press(screen.getByText('Create Product'));

    expect(screen.getByText('Product name is required.')).toBeTruthy();
    expect(screen.getByText('Selling price is required.')).toBeTruthy();
    expect(screen.getByText('Unit is required.')).toBeTruthy();
    expect(screen.getByText('Low stock threshold is required.')).toBeTruthy();
    expect(submit).not.toHaveBeenCalled();
  });

  it('normalizes and submits a valid decimal product once', async () => {
    const submit = jest.fn().mockResolvedValue(undefined);
    const screen = await render(
      <ProductForm
        actionLabel="Create Product"
        loading={false}
        loadingLabel="Creating Product…"
        onSubmit={submit}
      />,
    );
    await fireEvent.changeText(screen.getByLabelText('Product Name'), '  Mango Box  ');
    await fireEvent.changeText(screen.getByLabelText('Selling Price'), '125.50');
    await fireEvent.changeText(screen.getByLabelText('Low Stock Threshold'), '2.500');
    await fireEvent.press(screen.getByText('Box'));
    await fireEvent.press(screen.getByText('Create Product'));

    expect(submit).toHaveBeenCalledTimes(1);
    expect(submit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Mango Box',
        selling_price: '125.50',
        unit: 'box',
        low_stock_threshold: '2.500',
      }),
    );
  });
});
