import { fireEvent, render } from '@testing-library/react-native';

import { ActionCard, BottomNavigation, NavigationListItem } from '@/design-system';

describe('commercial navigation controls', () => {
  it('exposes a persistent, accessible selected bottom-navigation destination', async () => {
    const openSales = jest.fn();
    const screen = await render(
      <BottomNavigation
        items={[
          { icon: '🏠', key: 'home', label: 'Home', onPress: jest.fn(), selected: true },
          { icon: '💰', key: 'sales', label: 'Sales', onPress: openSales },
          { icon: '👥', key: 'customers', label: 'Customers', onPress: jest.fn() },
          { icon: '📦', key: 'products', label: 'Products', onPress: jest.fn() },
          { icon: '☰', key: 'more', label: 'More', onPress: jest.fn() },
        ]}
      />,
    );

    expect(screen.getByRole('tab', { name: 'Home' }).props.accessibilityState).toEqual({
      selected: true,
    });
    fireEvent.press(screen.getByRole('tab', { name: 'Sales' }));

    expect(openSales).toHaveBeenCalledTimes(1);
  });

  it('opens a dashboard quick action with one press', async () => {
    const onPress = jest.fn();
    const screen = await render(
      <ActionCard
        description="Create, review, and post sales."
        icon="💰"
        onPress={onPress}
        title="Sales"
      />,
    );

    fireEvent.press(screen.getByRole('button', { name: 'Sales' }));

    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('renders More destinations as labelled material-style rows', async () => {
    const onPress = jest.fn();
    const screen = await render(
      <NavigationListItem
        icon="📊"
        onPress={onPress}
        subtitle="Open read-only business reports and exports."
        title="Reports"
      />,
    );

    fireEvent.press(screen.getByRole('button', { name: 'Reports' }));

    expect(onPress).toHaveBeenCalledTimes(1);
  });
});
