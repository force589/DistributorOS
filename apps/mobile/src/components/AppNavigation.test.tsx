import { fireEvent, render } from '@testing-library/react-native';

import { appIcons } from '@/design/icons';
import { ActionCard, BottomNavigation, IconButton, NavigationListItem } from '@/design-system';

describe('commercial navigation controls', () => {
  it('exposes a persistent, accessible selected bottom-navigation destination', async () => {
    const openSales = jest.fn();
    const screen = await render(
      <BottomNavigation
        items={[
          { icon: appIcons.home, key: 'home', label: 'Home', onPress: jest.fn(), selected: true },
          { icon: appIcons.sales, key: 'sales', label: 'Sales', onPress: openSales },
          { icon: appIcons.customers, key: 'customers', label: 'Customers', onPress: jest.fn() },
          { icon: appIcons.products, key: 'products', label: 'Products', onPress: jest.fn() },
          { icon: appIcons.more, key: 'more', label: 'More', onPress: jest.fn() },
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
        icon={appIcons.sales}
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
        icon={appIcons.reports}
        onPress={onPress}
        subtitle="Open read-only business reports and exports."
        title="Reports"
      />,
    );

    fireEvent.press(screen.getByRole('button', { name: 'Reports' }));

    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('requires an accessible label for icon-only actions', async () => {
    const onPress = jest.fn();
    const screen = await render(
      <IconButton
        accessibilityLabel="Open settings"
        icon={appIcons.settings}
        onPress={onPress}
      />,
    );

    fireEvent.press(screen.getByRole('button', { name: 'Open settings' }));

    expect(onPress).toHaveBeenCalledTimes(1);
  });
});
